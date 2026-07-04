"""ベクトル化バックテストエンジン。

ルックアヘッド防止の中核:
- リバランス時点 ts で決めたウェイトは ts の「次のバー」から損益が発生する。
  実装はウェイトを1時間グリッドに展開(ffill)した後、1バーシフトして
  リターン行列に掛ける。この挙動は tests/test_backtest.py の回帰テストで固定。
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .costs import funding_pnl, trading_costs


@dataclass
class BacktestResult:
    returns: pd.DataFrame        # columns: gross, cost, funding, net(全て資本比)
    held_weights: pd.DataFrame   # バーごとの保有ウェイト
    equity: pd.Series            # 複利エクイティカーブ(初期資本基準)
    asset_returns: pd.DataFrame  # バーごとの資産リターン(指標計算用)


def run_backtest(
    closes: pd.DataFrame,
    weights: pd.DataFrame,
    funding: pd.DataFrame,
    fee_bps: float,
    slippage_bps: float,
    initial_capital: float = 10_000.0,
) -> BacktestResult:
    """closes: 1hの終値パネル。weights: リバランス時点のみの目標ウェイト。
    funding: 資金調達率パネル(8hごとの行のみ値を持つ)。
    """
    closes = closes.sort_index()
    asset_returns = closes.pct_change(fill_method=None)

    # リバランス時点の目標ウェイトを1時間グリッドへ展開し、
    # 1バーシフト = 「決定の翌バーから保有」
    expanded = weights.reindex(closes.index).ffill().fillna(0.0)
    held = expanded.shift(1).fillna(0.0)

    # 価格が存在しないバーの保有はリターン0として扱う(欠損データ)
    gross = (held * asset_returns).sum(axis=1, min_count=1).fillna(0.0)
    cost = trading_costs(held, fee_bps=fee_bps, slippage_bps=slippage_bps)
    fund = funding_pnl(held, funding)
    net = gross - cost + fund

    returns = pd.DataFrame({
        "gross": gross, "cost": cost, "funding": fund, "net": net,
    })
    equity = (1.0 + net).cumprod() * initial_capital
    return BacktestResult(returns=returns, held_weights=held,
                          equity=equity, asset_returns=asset_returns)


def make_rebalance_timestamps(index: pd.DatetimeIndex,
                              frequency_hours: int) -> pd.DatetimeIndex:
    """データのインデックスからリバランス時点を作る(UTC 00:00 起点で等間隔)。"""
    anchored = index[(index.hour % frequency_hours == 0)]
    if frequency_hours >= 24:
        anchored = index[index.hour == 0]
    return anchored
