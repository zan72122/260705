#!/usr/bin/env python3
"""バックテスト実行エントリポイント。

    python scripts/run_backtest.py --config config/base.yaml

data/ohlcv, data/funding の parquet を読み、指標テーブルとエクイティカーブを
data/results/<タイムスタンプ>/ に出力する。
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qtrader.backtest.engine import make_rebalance_timestamps, run_backtest
from qtrader.backtest.report import write_report
from qtrader.config import load_config
from qtrader.data.store import ParquetStore
from qtrader.data.universe import build_universe_mask
from qtrader.portfolio.construction import scores_to_weights
from qtrader.signals.momentum import CrossSectionalMomentum

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("run_backtest")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--out", default=None, help="出力先(既定: data/results/<UTC時刻>)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    store = ParquetStore(cfg.data.data_dir)

    symbols = store.list_symbols("ohlcv")
    if not symbols:
        logger.error("データがありません。先に scripts/fetch_data.py を実行してください")
        sys.exit(1)
    logger.info("%d 銘柄のデータを読込", len(symbols))

    closes = store.load_panel("ohlcv", "close")
    quote_volume = store.load_panel("ohlcv", "quote_volume")
    funding = store.load_panel("funding", "funding_rate")

    # ホールドアウトの温存(docs/theory.md §6): 既定では末尾を封印して使わない
    if not cfg.backtest.use_holdout and 0 < cfg.backtest.holdout_fraction < 1:
        cut = int(len(closes) * (1 - cfg.backtest.holdout_fraction))
        holdout_start = closes.index[cut]
        closes = closes.iloc[:cut]
        quote_volume = quote_volume.iloc[:cut]
        funding = funding[funding.index < holdout_start]
        logger.info("ホールドアウト温存: %s 以降(%.0f%%)は使用しない",
                    holdout_start, cfg.backtest.holdout_fraction * 100)

    rebalance_ts = make_rebalance_timestamps(closes.index, cfg.rebalance.frequency_hours)
    logger.info("リバランス %d 回(%dh間隔)", len(rebalance_ts), cfg.rebalance.frequency_hours)

    universe = build_universe_mask(
        quote_volume, rebalance_ts,
        top_n=cfg.universe.top_n,
        volume_lookback_days=cfg.universe.volume_lookback_days,
        min_listing_days=cfg.universe.min_listing_days,
    )
    signal = CrossSectionalMomentum(lookback_bars=cfg.signal.lookback_hours)
    scores = signal.compute(closes)
    weights = scores_to_weights(scores, universe, quantile=cfg.portfolio.quantile)

    result = run_backtest(
        closes, weights, funding,
        fee_bps=cfg.costs.fee_bps,
        slippage_bps=cfg.costs.slippage_bps,
        initial_capital=cfg.backtest.initial_capital,
    )

    out_dir = args.out or (
        Path(cfg.data.data_dir) / "results"
        / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    metrics = write_report(
        result, out_dir,
        config_snapshot=dataclasses.asdict(cfg),
        benchmark_symbol=cfg.backtest.benchmark_symbol,
    )

    logger.info("結果を %s に出力", out_dir)
    summary = pd.Series(metrics)
    print("\n=== バックテスト結果(コスト後) ===")
    print(summary.to_string())


if __name__ == "__main__":
    main()
