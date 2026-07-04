"""バックテストエンジンのテスト: 既知解との一致とルックアヘッド防止の回帰テスト。"""

import numpy as np
import pandas as pd

from qtrader.backtest.engine import make_rebalance_timestamps, run_backtest


def make_index(n):
    return pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")


def test_known_solution_two_symbols():
    """A: +1%/バー、B: -1%/バー。+0.5/-0.5のL/Sなら毎バー+1%(コスト前)。"""
    n = 10
    idx = make_index(n)
    closes = pd.DataFrame({
        "A": 100 * 1.01 ** np.arange(n),
        "B": 100 * 0.99 ** np.arange(n),
    }, index=idx)
    weights = pd.DataFrame({"A": [0.5], "B": [-0.5]}, index=idx[[0]])

    result = run_backtest(closes, weights, funding=pd.DataFrame(),
                          fee_bps=10, slippage_bps=0)
    gross = result.returns["gross"]
    # 保有はバー1から。毎バーのgross = 0.5×1% + (−0.5)×(−1%) = 1%
    assert np.isclose(gross.iloc[0], 0.0)
    assert np.allclose(gross.iloc[1:], 0.01)
    # コストは建玉構築バー(バー1)のみ: ターンオーバー1.0 × 10bps
    cost = result.returns["cost"]
    assert np.isclose(cost.iloc[1], 0.0010)
    assert np.isclose(cost.iloc[2:].sum(), 0.0)


def test_lookahead_prevention_regression():
    """最終バーで急騰する銘柄を最終リバランスでロングしても、その急騰は取れない。

    ウェイトの1バーシフトが失われるとこのテストが落ちる(回帰テスト)。
    """
    n = 6
    idx = make_index(n)
    prices_a = [100.0] * (n - 1) + [200.0]  # 最終バーで2倍
    closes = pd.DataFrame({"A": prices_a, "B": [100.0] * n}, index=idx)
    # 最終バーの時点でAをロング(急騰を見てから建てたことに相当)
    weights = pd.DataFrame({"A": [1.0], "B": [-1.0]}, index=idx[[n - 1]])

    result = run_backtest(closes, weights, funding=pd.DataFrame(),
                          fee_bps=0, slippage_bps=0)
    # 決定の翌バーは存在しない → 損益ゼロでなければルックアヘッド
    assert np.isclose(result.returns["gross"].sum(), 0.0)

    # 対照: 最初のリバランスで建てていれば急騰を取れる
    weights_early = pd.DataFrame({"A": [1.0], "B": [-1.0]}, index=idx[[0]])
    result2 = run_backtest(closes, weights_early, funding=pd.DataFrame(),
                           fee_bps=0, slippage_bps=0)
    assert result2.returns["gross"].sum() > 0.9  # A の +100% × 1.0


def test_funding_applied_at_funding_bars():
    n = 24
    idx = make_index(n)
    closes = pd.DataFrame({"A": [100.0] * n, "B": [100.0] * n}, index=idx)
    weights = pd.DataFrame({"A": [1.0], "B": [-1.0]}, index=idx[[0]])
    # 08:00 UTC にAのみ正のファンディング
    f_idx = idx[idx.hour == 8]
    funding = pd.DataFrame({"A": [1e-3]}, index=f_idx)

    result = run_backtest(closes, weights, funding, fee_bps=0, slippage_bps=0)
    fund = result.returns["funding"]
    # ロング1.0 × レート1e-3 の支払い
    assert np.isclose(fund.loc[f_idx[0]], -1e-3)
    assert np.isclose(fund.drop(f_idx[0]).abs().sum(), 0.0)


def test_equity_compounds_net_returns():
    n = 5
    idx = make_index(n)
    closes = pd.DataFrame({
        "A": 100 * 1.02 ** np.arange(n),
        "B": [100.0] * n,
    }, index=idx)
    weights = pd.DataFrame({"A": [0.5], "B": [-0.5]}, index=idx[[0]])
    result = run_backtest(closes, weights, funding=pd.DataFrame(),
                          fee_bps=0, slippage_bps=0, initial_capital=10_000)
    expected = 10_000 * (1 + result.returns["net"]).prod()
    assert np.isclose(result.equity.iloc[-1], expected)


def test_make_rebalance_timestamps_daily():
    idx = make_index(72)
    ts = make_rebalance_timestamps(idx, frequency_hours=24)
    assert all(t.hour == 0 for t in ts)
    assert len(ts) == 3

    ts8 = make_rebalance_timestamps(idx, frequency_hours=8)
    assert all(t.hour in (0, 8, 16) for t in ts8)
    assert len(ts8) == 9
