"""コストモデル: 手数料・スリッページ・ファンディングPnL。"""

from __future__ import annotations

import pandas as pd


def trading_costs(held_weights: pd.DataFrame,
                  fee_bps: float, slippage_bps: float) -> pd.Series:
    """バーごとの取引コスト(資本比)。

    held_weights: バーごとに保有していたウェイト(シフト適用済み)。
    ウェイト変化の絶対値合計 = ターンオーバー(片道)に
    (手数料+スリッページ)率を掛ける。
    """
    turnover = held_weights.diff().abs().sum(axis=1)
    # 初回バーは diff が NaN になるため、初期ポジション構築分を明示的に計上
    if len(held_weights) > 0:
        turnover.iloc[0] = held_weights.iloc[0].abs().sum()
    rate = (fee_bps + slippage_bps) / 10_000
    return turnover * rate


def funding_pnl(held_weights: pd.DataFrame, funding: pd.DataFrame) -> pd.Series:
    """バーごとのファンディングPnL(資本比)。

    funding: (timestamp × symbol) の資金調達率パネル。授受タイミング
    (00/08/16 UTC)の行のみ値を持つ。
    符号: ロング(w>0)は正レートで支払い → PnL = -w × rate
    """
    if funding.empty:
        return pd.Series(0.0, index=held_weights.index)
    aligned = funding.reindex(index=held_weights.index,
                              columns=held_weights.columns)
    pnl = -(held_weights * aligned).sum(axis=1)
    return pnl.fillna(0.0)
