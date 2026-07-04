"""バックテスト結果のレポート出力(指標テーブル+図)。"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import yaml

from .engine import BacktestResult
from .metrics import compute_metrics, monthly_returns_table

_PERCENT_KEYS = {
    "ann_return_net", "ann_vol_net", "max_drawdown",
    "total_gross", "total_cost", "total_funding", "total_net",
    "long_contribution", "short_contribution",
}


def _fmt(key: str, value) -> str:
    if isinstance(value, float):
        if key in _PERCENT_KEYS:
            return f"{value:.2%}"
        return f"{value:.3f}"
    return str(value)


def write_report(result: BacktestResult, out_dir: str | Path,
                 config_snapshot: dict | None = None,
                 benchmark_symbol: str = "BTCUSDT") -> dict:
    """指標テーブル(md/csv)・エクイティカーブ(png)・設定スナップショットを出力。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    metrics = compute_metrics(result, benchmark_symbol=benchmark_symbol)
    monthly = monthly_returns_table(result)

    # 指標テーブル
    pd.Series(metrics).to_csv(out / "metrics.csv", header=["value"])
    lines = ["# バックテスト結果", "", "| 指標 | 値 |", "|---|---|"]
    lines += [f"| {k} | {_fmt(k, v)} |" for k, v in metrics.items()]
    lines += ["", "## 月次リターン(net)", "", "| 月 | リターン |", "|---|---|"]
    lines += [f"| {idx} | {row['return']:.2%} |" for idx, row in monthly.iterrows()]
    (out / "metrics.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # エクイティカーブ + ドローダウン
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True,
                                   height_ratios=[3, 1])
    result.equity.plot(ax=ax1, color="tab:blue")
    ax1.set_title("Equity curve (net of costs)")
    ax1.set_ylabel("Equity (USDT)")
    ax1.grid(alpha=0.3)
    drawdown = result.equity / result.equity.cummax() - 1
    drawdown.plot(ax=ax2, color="tab:red")
    ax2.set_ylabel("Drawdown")
    ax2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out / "equity.png", dpi=120)
    plt.close(fig)

    # 再現性のための設定スナップショット
    if config_snapshot is not None:
        (out / "config_snapshot.yaml").write_text(
            yaml.safe_dump(config_snapshot, allow_unicode=True), encoding="utf-8")

    return metrics
