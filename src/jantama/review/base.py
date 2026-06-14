"""解析エンジンの共通インターフェース。

実装を差し替えられるようにしておく（Mortal / 将来の他エンジン）。
入力は mjai 形式のイベント列、出力は評価済みの DecisionPoint 群。
"""

from __future__ import annotations

from typing import Protocol

from ..models import DecisionPoint


class Reviewer(Protocol):
    def review(self, mjai_events: list[dict]) -> list[DecisionPoint]:
        """mjai イベント列を解析し、各意思決定局面を評価して返す。"""
        ...
