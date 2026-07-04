"""クロスセクショナル・モメンタム。

時刻tのスコア = 過去 lookback_bars 本の対数リターン。
横断比較(ランク)はポートフォリオ構築側で行うため、ここでは生スコアを返す。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Signal


class CrossSectionalMomentum(Signal):
    def __init__(self, lookback_bars: int):
        if lookback_bars < 1:
            raise ValueError("lookback_bars は1以上")
        self.lookback_bars = lookback_bars

    def compute(self, closes: pd.DataFrame,
                funding: pd.DataFrame | None = None) -> pd.DataFrame:
        past = closes.shift(self.lookback_bars)
        with np.errstate(divide="ignore", invalid="ignore"):
            score = np.log(closes / past)
        return score
