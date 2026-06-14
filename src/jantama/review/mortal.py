"""Mortal を解析エンジンとして使う Reviewer。

オープンソースの mjai-reviewer (Equim-chan/mjai-reviewer) を Mortal エンジンで
起動し、出力 JSON を DecisionPoint へ変換する。

このコンテナには Mortal のモデル重み(.pth)が無いため、ここでは「呼び出し方を
組み立てて実行し、結果を取り込む」アダプタを提供する。実際に動かすには:
  1. mjai-reviewer をビルド/入手して MJAI_REVIEWER_PATH に設定
  2. Mortal のモデル重みを用意し MORTAL_MODEL_PATH に設定
詳細は README を参照。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..config import Config
from ..models import DecisionPoint
from .parser import parse_review_json


class EngineUnavailableError(RuntimeError):
    """解析エンジン（mjai-reviewer / Mortal）が利用できないときに送出。"""


class MortalReviewer:
    def __init__(self, config: Config | None = None, actor: int = 0) -> None:
        self.config = config or Config.from_env()
        self.actor = actor

    def available(self) -> bool:
        """mjai-reviewer 実行ファイルが PATH 上に存在するか。"""
        return shutil.which(self.config.mjai_reviewer_path) is not None

    def build_command(self, in_path: str, out_path: str) -> list[str]:
        """mjai-reviewer の起動コマンドを組み立てる。

        フラグはバージョンにより異なるため、ここを調整ポイントとする。
        """
        cmd = [
            self.config.mjai_reviewer_path,
            "-e", "mortal",
            "-i", in_path,
            "-a", str(self.actor),
            "--json",
            "-o", out_path,
            "--no-open",
        ]
        if self.config.mortal_model_path:
            cmd += ["--mortal-exe", "mortal", "--mortal-cfg", self.config.mortal_model_path]
        return cmd

    def review(self, mjai_events: list[dict]) -> list[DecisionPoint]:
        if not self.available():
            raise EngineUnavailableError(
                f"mjai-reviewer が見つかりません (path={self.config.mjai_reviewer_path!r})。"
                " MJAI_REVIEWER_PATH と MORTAL_MODEL_PATH を設定してください。README参照。"
            )
        with tempfile.TemporaryDirectory() as tmp:
            in_path = Path(tmp) / "game.mjai.json"
            out_path = Path(tmp) / "review.json"
            # mjai ログは改行区切り JSON
            in_path.write_text(
                "\n".join(json.dumps(ev, ensure_ascii=False) for ev in mjai_events),
                encoding="utf-8",
            )
            cmd = self.build_command(str(in_path), str(out_path))
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                raise EngineUnavailableError(
                    f"mjai-reviewer の実行に失敗しました (code={proc.returncode}).\n"
                    f"stderr: {proc.stderr.strip()[:500]}"
                )
            raw = out_path.read_text(encoding="utf-8") if out_path.exists() else proc.stdout
            data = json.loads(raw)
        return parse_review_json(data, player_id=self.actor)
