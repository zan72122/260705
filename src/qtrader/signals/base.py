"""シグナルの共通インターフェース。

すべてのシグナルは「(timestamp × symbol) の入力パネル → 同形状のスコアDF」を返す
純粋関数として実装する。バックテストは過去全期間に一括適用し、
実行層(ペーパー/ライブ)は最新時点に適用するだけで、ロジックは同一。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Signal(ABC):
    """スコアは「大きいほどロングしたい」に統一する。"""

    @abstractmethod
    def compute(self, closes: pd.DataFrame,
                funding: pd.DataFrame | None = None) -> pd.DataFrame:
        """closes: (timestamp × symbol) の終値パネル。
        funding: (timestamp × symbol) のファンディングレートパネル(使うシグナルのみ)。

        戻り値: closes と同形状のスコアDF。時刻tの行は t 以前の確定足のみから
        計算しなければならない(ルックアヘッド禁止)。
        """
