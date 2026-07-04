"""スコア → ドルニュートラルなウェイト行列。

各リバランス時点で:
1. ユニバースマスクを適用し、スコアが有効な銘柄だけを対象にする
2. スコアでランク付けし、上位 quantile をロング・下位 quantile をショート
3. 各サイドを等ウェイトにし、ロング合計 +0.5 / ショート合計 -0.5 に正規化
   → Σw = 0(ドルニュートラル)、Σ|w| = 1(グロス = 資本×1倍)
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def scores_to_weights(
    scores: pd.DataFrame,
    universe_mask: pd.DataFrame,
    quantile: float,
    min_names_per_side: int = 3,
) -> pd.DataFrame:
    """(リバランス時点 × 銘柄) のウェイト行列を返す。

    scores: (timestamp × symbol)。universe_mask のインデックス(リバランス時点)に
            合わせて直近の確定スコアを参照する。
    universe_mask: build_universe_mask の出力(リバランス時点 × 銘柄, bool)
    quantile: 片側の分位幅(0 < q <= 0.5)
    min_names_per_side: 片側の最低銘柄数。満たない時点はノーポジション
    """
    if not 0 < quantile <= 0.5:
        raise ValueError("quantile は (0, 0.5] の範囲")

    weights = pd.DataFrame(0.0, index=universe_mask.index,
                           columns=universe_mask.columns)
    for ts in universe_mask.index:
        # t以前の確定スコアのみ参照(ルックアヘッド防止)
        idx = scores.index.searchsorted(ts, side="right") - 1
        if idx < 0:
            continue
        row = scores.iloc[idx]
        valid = row.where(universe_mask.loc[ts]).dropna()
        n = len(valid)
        n_side = int(np.floor(n * quantile))
        if n_side < min_names_per_side:
            continue
        ranked = valid.sort_values()
        shorts = ranked.index[:n_side]
        longs = ranked.index[-n_side:]
        weights.loc[ts, longs] = 0.5 / n_side
        weights.loc[ts, shorts] = -0.5 / n_side
    return weights
