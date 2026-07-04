"""コストモデル(手数料・スリッページ・ファンディング)の単体テスト。"""

import numpy as np
import pandas as pd

from qtrader.backtest.costs import funding_pnl, trading_costs


def make_index(n):
    return pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")


def test_trading_costs_initial_build_and_rebalance():
    idx = make_index(4)
    held = pd.DataFrame({
        "A": [0.5, 0.5, -0.5, -0.5],
        "B": [-0.5, -0.5, 0.5, 0.5],
    }, index=idx)
    costs = trading_costs(held, fee_bps=10, slippage_bps=0)
    # 初回: ターンオーバー |0.5|+|−0.5| = 1.0 → 1.0 × 10bps
    assert np.isclose(costs.iloc[0], 1.0 * 0.0010)
    # 反転リバランス: |−0.5−0.5|×2 = 2.0 → 2.0 × 10bps
    assert np.isclose(costs.iloc[2], 2.0 * 0.0010)
    # 変化なしのバーはコストゼロ
    assert np.isclose(costs.iloc[1], 0.0)
    assert np.isclose(costs.iloc[3], 0.0)


def test_funding_pnl_signs():
    """ロングは正レートで支払い、ショートは受取り。"""
    idx = make_index(3)
    held = pd.DataFrame({"A": [0.5, 0.5, 0.5], "B": [-0.5, -0.5, -0.5]}, index=idx)
    funding = pd.DataFrame({"A": [np.nan, 1e-4, np.nan],
                            "B": [np.nan, 1e-4, np.nan]}, index=idx)
    pnl = funding_pnl(held, funding)
    # ロング: -0.5×1e-4(支払い)、ショート: +0.5×1e-4(受取り)→ 相殺で0
    assert np.isclose(pnl.iloc[1], 0.0)
    assert np.isclose(pnl.iloc[0], 0.0)

    held_long_only = pd.DataFrame({"A": [1.0, 1.0, 1.0]}, index=idx)
    funding_a = pd.DataFrame({"A": [np.nan, 1e-4, np.nan]}, index=idx)
    pnl2 = funding_pnl(held_long_only, funding_a)
    assert np.isclose(pnl2.iloc[1], -1e-4)  # ロングの支払い


def test_funding_pnl_empty():
    idx = make_index(2)
    held = pd.DataFrame({"A": [0.5, 0.5]}, index=idx)
    pnl = funding_pnl(held, pd.DataFrame())
    assert (pnl == 0).all()
