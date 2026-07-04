"""シグナルとポートフォリオ構築の単体テスト(手計算できる小データ)。"""

import numpy as np
import pandas as pd
import pytest

from qtrader.portfolio.construction import scores_to_weights
from qtrader.signals.momentum import CrossSectionalMomentum


def make_index(n, freq="1h"):
    return pd.date_range("2024-01-01", periods=n, freq=freq, tz="UTC")


def test_momentum_score_is_lookback_log_return():
    idx = make_index(5)
    closes = pd.DataFrame({"A": [100, 110, 121, 133.1, 146.41]}, index=idx)
    sig = CrossSectionalMomentum(lookback_bars=2)
    scores = sig.compute(closes)
    # t=2 のスコア = log(121/100)
    assert np.isclose(scores.iloc[2]["A"], np.log(121 / 100))
    assert scores.iloc[:2]["A"].isna().all()


def test_weights_are_dollar_neutral_and_unit_gross():
    idx = make_index(3)
    rebalance = idx[[2]]
    # 10銘柄、スコアは明確な順序
    symbols = [f"S{i}" for i in range(10)]
    scores = pd.DataFrame([np.arange(10.0)] * 3, index=idx, columns=symbols)
    mask = pd.DataFrame(True, index=rebalance, columns=symbols)

    w = scores_to_weights(scores, mask, quantile=0.3)
    row = w.loc[rebalance[0]]
    # Σw = 0(ドルニュートラル)、Σ|w| = 1(グロス1倍)
    assert np.isclose(row.sum(), 0.0)
    assert np.isclose(row.abs().sum(), 1.0)
    # 上位3銘柄がロング、下位3銘柄がショート、等ウェイト
    assert np.allclose(row[["S9", "S8", "S7"]], 0.5 / 3)
    assert np.allclose(row[["S0", "S1", "S2"]], -0.5 / 3)
    assert np.allclose(row[["S3", "S4", "S5", "S6"]], 0.0)


def test_weights_respect_universe_mask():
    idx = make_index(2)
    rebalance = idx[[1]]
    symbols = [f"S{i}" for i in range(6)]
    scores = pd.DataFrame([np.arange(6.0)] * 2, index=idx, columns=symbols)
    mask = pd.DataFrame(True, index=rebalance, columns=symbols)
    mask.loc[rebalance[0], "S5"] = False  # 最高スコア銘柄をユニバース外に

    w = scores_to_weights(scores, mask, quantile=0.2, min_names_per_side=1)
    row = w.loc[rebalance[0]]
    assert row["S5"] == 0.0
    assert row["S4"] > 0  # 次点がロングになる


def test_no_position_when_too_few_names():
    idx = make_index(2)
    rebalance = idx[[1]]
    symbols = ["A", "B", "C", "D"]
    scores = pd.DataFrame([[1.0, 2.0, 3.0, 4.0]] * 2, index=idx, columns=symbols)
    mask = pd.DataFrame(True, index=rebalance, columns=symbols)
    # 4銘柄 × 20% = 0.8 → floor 0 < min_names_per_side → ノーポジション
    w = scores_to_weights(scores, mask, quantile=0.2, min_names_per_side=3)
    assert (w.loc[rebalance[0]] == 0).all()


def test_weights_use_only_past_scores():
    """リバランス時点より未来のスコアを参照しないこと。"""
    idx = make_index(4)
    rebalance = idx[[1]]
    symbols = ["A", "B"]
    scores = pd.DataFrame(
        [[1.0, 2.0], [1.0, 2.0], [100.0, -100.0], [100.0, -100.0]],
        index=idx, columns=symbols)
    mask = pd.DataFrame(True, index=rebalance, columns=symbols)
    w = scores_to_weights(scores, mask, quantile=0.5, min_names_per_side=1)
    # t=1 時点のスコア(B>A)に基づくはず。未来(t=2以降)の逆転(A>B)は見ない
    assert w.loc[rebalance[0], "B"] > 0
    assert w.loc[rebalance[0], "A"] < 0


def test_invalid_quantile_raises():
    idx = make_index(1)
    df = pd.DataFrame({"A": [1.0]}, index=idx)
    mask = pd.DataFrame(True, index=idx, columns=["A"])
    with pytest.raises(ValueError):
        scores_to_weights(df, mask, quantile=0.6)
