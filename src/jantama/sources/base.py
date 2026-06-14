"""牌譜入力源の共通インターフェース。"""

from __future__ import annotations

from typing import Protocol


class PaifuUnavailableError(RuntimeError):
    """牌譜を取得・変換できないときに送出。"""


class PaifuSource(Protocol):
    def load(self) -> list[dict]:
        """mjai 形式のイベント列（改行区切り JSON 相当のリスト）を返す。"""
        ...
