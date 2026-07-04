#!/usr/bin/env python3
"""市場データの取得・増分更新。

実データ(要ネットワーク):
    python scripts/fetch_data.py --days 730

合成データ(プラミング検証専用。収益性の評価には使えない):
    python scripts/fetch_data.py --synthetic
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qtrader.config import load_config
from qtrader.data.quality import check_ohlcv
from qtrader.data.store import ParquetStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("fetch_data")


def fetch_real(store: ParquetStore, interval: str, days: int) -> None:
    from qtrader.data.binance_client import BinanceFuturesClient

    client = BinanceFuturesClient()
    symbols = client.get_usdt_perp_symbols()
    logger.info("USDT建てperp %d 銘柄", len(symbols))
    default_start = datetime.now(timezone.utc) - timedelta(days=days)

    for i, sym in enumerate(symbols, 1):
        last = store.last_timestamp("ohlcv", sym)
        start = last.to_pydatetime() if last is not None else default_start
        ohlcv = client.get_klines(sym, interval, start=start)
        if not ohlcv.empty:
            store.save("ohlcv", sym, ohlcv)

        last_f = store.last_timestamp("funding", sym)
        start_f = last_f.to_pydatetime() if last_f is not None else default_start
        fund = client.get_funding_rates(sym, start=start_f)
        if not fund.empty:
            store.save("funding", sym, fund)

        logger.info("[%d/%d] %s: ohlcv+%d funding+%d", i, len(symbols), sym,
                    len(ohlcv), len(fund))


def fetch_synthetic(store: ParquetStore, days: int) -> None:
    from qtrader.data.synthetic import generate_synthetic_market

    logger.warning("合成データを生成します(プラミング検証専用)")
    ohlcv, funding = generate_synthetic_market(n_days=days)
    for sym, df in ohlcv.items():
        store.save("ohlcv", sym, df)
        store.save("funding", sym, funding[sym])
    logger.info("合成データ %d 銘柄 × %d 日を保存", len(ohlcv), days)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--days", type=int, default=None, help="取得日数(既定はconfig値)")
    parser.add_argument("--synthetic", action="store_true",
                        help="合成データを生成(ネットワーク不要、検証専用)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    days = args.days or cfg.data.history_days
    store = ParquetStore(cfg.data.data_dir)

    if args.synthetic:
        fetch_synthetic(store, days=min(days, 365))
    else:
        fetch_real(store, interval=cfg.data.interval, days=days)

    # 取得後の品質チェック
    n_warn = 0
    for sym in store.list_symbols("ohlcv"):
        df = store.load("ohlcv", sym)
        report = check_ohlcv(sym, df)
        if not report.ok:
            n_warn += 1
            logger.warning("%s: %s", sym, "; ".join(report.warnings))
    logger.info("品質チェック完了(警告 %d 銘柄)", n_warn)


if __name__ == "__main__":
    main()
