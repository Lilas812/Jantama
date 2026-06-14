"""ローカルの mjai ログを読み込む入力源。

対応形式:
  - mjai 改行区切り JSON (.jsonl / .mjai): 1 行 1 イベント
  - JSON 配列: [{...}, {...}, ...]
"""

from __future__ import annotations

import json
from pathlib import Path

from .base import PaifuUnavailableError


class LocalLogSource:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[dict]:
        if not self.path.exists():
            raise PaifuUnavailableError(f"ファイルが見つかりません: {self.path}")
        text = self.path.read_text(encoding="utf-8").strip()
        if not text:
            raise PaifuUnavailableError(f"空のファイルです: {self.path}")
        # まず JSON 配列として解釈を試す
        if text[0] == "[":
            data = json.loads(text)
            if not isinstance(data, list):
                raise PaifuUnavailableError("JSON 配列ではありません")
            return data
        # 改行区切り JSON
        events: list[dict] = []
        for i, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise PaifuUnavailableError(f"{i} 行目の JSON が不正です: {exc}") from exc
        return events
