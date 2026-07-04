"""E2Eスモークテスト: 合成データで シグナル→バックテスト→レポート を通す。"""

import pandas as pd

from qtrader.backtest.engine import make_rebalance_timestamps, run_backtest
from qtrader.backtest.report import write_report
from qtrader.data.quality import check_ohlcv
from qtrader.data.store import ParquetStore
from qtrader.data.synthetic import generate_synthetic_market
from qtrader.data.universe import build_universe_mask
from qtrader.portfolio.construction import scores_to_weights
from qtrader.signals.momentum import CrossSectionalMomentum


def test_end_to_end_pipeline(tmp_path):
    ohlcv, funding = generate_synthetic_market(n_symbols=12, n_days=150, seed=7)

    store = ParquetStore(tmp_path)
    for sym, df in ohlcv.items():
        store.save("ohlcv", sym, df)
        store.save("funding", sym, funding[sym])

    # 増分保存の重複排除を確認
    first = list(ohlcv)[0]
    store.save("ohlcv", first, ohlcv[first])
    reloaded = store.load("ohlcv", first)
    assert not reloaded["timestamp"].duplicated().any()

    # 品質チェックが完走する
    for sym in store.list_symbols("ohlcv"):
        check_ohlcv(sym, store.load("ohlcv", sym))

    closes = store.load_panel("ohlcv", "close")
    quote_volume = store.load_panel("ohlcv", "quote_volume")
    funding_panel = store.load_panel("funding", "funding_rate")
    assert not closes.empty

    rebalance_ts = make_rebalance_timestamps(closes.index, 24)
    universe = build_universe_mask(quote_volume, rebalance_ts, top_n=8,
                                   volume_lookback_days=10, min_listing_days=30)
    # ユニバースは各時点で top_n 以下
    assert (universe.sum(axis=1) <= 8).all()

    signal = CrossSectionalMomentum(lookback_bars=72)
    scores = signal.compute(closes)
    # 8銘柄 × 25% = 片側2銘柄なので最低銘柄数も2に合わせる
    weights = scores_to_weights(scores, universe, quantile=0.25,
                                min_names_per_side=2)

    # ドルニュートラル制約(ポジションがある時点のみ)
    active = weights.abs().sum(axis=1) > 0
    assert active.any()
    assert (weights[active].sum(axis=1).abs() < 1e-9).all()
    assert ((weights[active].abs().sum(axis=1) - 1).abs() < 1e-9).all()

    result = run_backtest(closes, weights, funding_panel,
                          fee_bps=5, slippage_bps=5)
    assert len(result.returns) == len(closes)
    assert result.equity.notna().all()

    out = tmp_path / "results"
    metrics = write_report(result, out, config_snapshot={"test": True})
    assert (out / "metrics.md").exists()
    assert (out / "metrics.csv").exists()
    assert (out / "equity.png").exists()
    assert (out / "config_snapshot.yaml").exists()
    assert "sharpe_net" in metrics
