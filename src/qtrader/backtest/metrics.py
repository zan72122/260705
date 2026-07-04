"""評価指標。すべてコスト後(net)を主指標とする。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .engine import BacktestResult

HOURS_PER_YEAR = 24 * 365


def compute_metrics(result: BacktestResult,
                    benchmark_symbol: str = "BTCUSDT",
                    bars_per_year: int = HOURS_PER_YEAR) -> dict:
    net = result.returns["net"]
    gross = result.returns["gross"]
    n = len(net)
    if n == 0:
        return {}
    years = n / bars_per_year

    ann_return = (1 + net).prod() ** (1 / years) - 1 if years > 0 else np.nan
    ann_vol = net.std() * np.sqrt(bars_per_year)
    sharpe = (net.mean() / net.std() * np.sqrt(bars_per_year)
              if net.std() > 0 else np.nan)

    # 最大ドローダウン
    equity = result.equity
    drawdown = equity / equity.cummax() - 1
    max_dd = drawdown.min()
    calmar = ann_return / abs(max_dd) if max_dd < 0 else np.nan

    # ターンオーバー(片道、年率)
    held = result.held_weights
    turnover = held.diff().abs().sum(axis=1)
    if len(held) > 0:
        turnover.iloc[0] = held.iloc[0].abs().sum()
    ann_turnover = turnover.sum() / years if years > 0 else np.nan

    # 対ベンチマークβ・相関(ニュートラル性の検証)
    beta = corr = np.nan
    if benchmark_symbol in result.asset_returns.columns:
        bench = result.asset_returns[benchmark_symbol]
        pair = pd.concat([net, bench], axis=1, keys=["net", "bench"]).dropna()
        if len(pair) > 10 and pair["bench"].var() > 0:
            beta = pair["net"].cov(pair["bench"]) / pair["bench"].var()
            corr = pair["net"].corr(pair["bench"])

    # ロング/ショート寄与の分解
    long_contrib = (held.clip(lower=0) * result.asset_returns).sum(axis=1).sum()
    short_contrib = (held.clip(upper=0) * result.asset_returns).sum(axis=1).sum()

    return {
        "bars": n,
        "years": round(years, 2),
        "ann_return_net": ann_return,
        "ann_vol_net": ann_vol,
        "sharpe_net": sharpe,
        "max_drawdown": max_dd,
        "calmar": calmar,
        "ann_turnover_oneway": ann_turnover,
        "beta_vs_benchmark": beta,
        "corr_vs_benchmark": corr,
        "total_gross": gross.sum(),
        "total_cost": -result.returns["cost"].sum(),
        "total_funding": result.returns["funding"].sum(),
        "total_net": net.sum(),
        "long_contribution": long_contrib,
        "short_contribution": short_contrib,
    }


def monthly_returns_table(result: BacktestResult) -> pd.DataFrame:
    """月次リターン(net、複利)テーブル。"""
    net = result.returns["net"]
    monthly = (1 + net).resample("ME").prod() - 1
    table = monthly.to_frame("return")
    table.index = table.index.strftime("%Y-%m")
    return table
