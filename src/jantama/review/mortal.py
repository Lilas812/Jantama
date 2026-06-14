"""mjai-reviewer（Mortal / akochan エンジン）を呼び出す Reviewer。

オープンソースの mjai-reviewer (Equim-chan/mjai-reviewer) を起動し、出力 JSON を
DecisionPoint へ変換する。エンジンは config.engine で選ぶ:
  - "mortal" : 高精度。学習済みモデル重みが必要。
  - "akochan": 探索ベースの強AI。モデル重み不要（ビルドは必要）。
入力は天鳳形式（雀魂は tensoul 等で天鳳形式へ変換）。出力 JSON の mjai_log で
手牌・盤面・押し引きを補完する。セットアップは docs/SETUP.md を参照。
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..config import Config
from ..models import DecisionPoint
from .parser import parse_and_enrich


class EngineUnavailableError(RuntimeError):
    """解析エンジン（mjai-reviewer / Mortal / akochan）が利用できないときに送出。"""


class MjaiReviewer:
    """mjai-reviewer を Mortal または akochan エンジンで呼び出すアダプタ。"""

    def __init__(self, config: Config | None = None, actor: int = 0) -> None:
        self.config = config or Config.from_env()
        if not 0 <= actor <= 3:
            raise ValueError(f"actor は 0〜3 で指定してください: {actor}")
        self.actor = actor
        self.engine = self.config.engine if self.config.engine in ("mortal", "akochan") else "mortal"

    def available(self) -> bool:
        """mjai-reviewer 実行ファイルが PATH 上に存在するか。"""
        if self.config.mjai_reviewer_cmd:  # コマンド上書き時は存在チェックを省く
            return True
        return shutil.which(self.config.mjai_reviewer_path) is not None

    def _engine_opts(self) -> list[str]:
        """エンジン固有のオプション。"""
        if self.engine == "mortal":
            if self.config.mortal_model_path:
                return ["--mortal-exe", "mortal", "--mortal-cfg", self.config.mortal_model_path]
            return []
        opts: list[str] = []  # akochan
        if self.config.akochan_dir:
            opts += ["--akochan-dir", self.config.akochan_dir]
        if self.config.akochan_tactics:
            opts += ["--akochan-tactics", self.config.akochan_tactics]
        return opts

    def build_command(self, in_path: str, out_path: str) -> list[str]:
        """ファイル入力(-i)の起動コマンドを組み立てる。

        MJAI_REVIEWER_CMD（{in}{out}{actor}{model} を置換）があればそれを使う。
        無ければ既定の組み立て。フラグが合わなければテンプレで上書きできる。
        """
        if self.config.mjai_reviewer_cmd:
            template = self.config.mjai_reviewer_cmd.format(
                in_=in_path, out=out_path, actor=self.actor,
                model=self.config.mortal_model_path or "",
                **{"in": in_path},  # {in} エイリアス
            )
            return shlex.split(template)
        return [
            self.config.mjai_reviewer_path,
            "-e", self.engine,
            "-i", in_path,
            "-a", str(self.actor),
            "--json", "-o", out_path, "--no-open",
            *self._engine_opts(),
        ]

    def _remote_command(self, flag: str, value: str, out_path: str) -> list[str]:
        """天鳳ID(-t) / URL(-u) 入力の起動コマンド。"""
        return [
            self.config.mjai_reviewer_path, "-e", self.engine, flag, value,
            "-a", str(self.actor), "--json", "-o", out_path, "--no-open",
            *self._engine_opts(),
        ]

    def _command_for(self, source: str, tmpdir: str, out_path: str) -> list[str]:
        """入力の種類を判別して起動コマンドを返す（-i ファイル / -t ID / -u URL）。"""
        s = source.strip()
        if s.startswith(("http://", "https://")):
            return self._remote_command("-u", s, out_path)
        if Path(source).exists():  # 天鳳形式のファイル
            return self.build_command(str(Path(source)), out_path)
        if s[:1] in "{[":  # 天鳳 JSON 文字列
            in_path = Path(tmpdir) / "tenhou.json"
            in_path.write_text(s, encoding="utf-8")
            return self.build_command(str(in_path), out_path)
        return self._remote_command("-t", s, out_path)  # 天鳳ログID とみなす

    def review(self, source: str) -> list[DecisionPoint]:
        """天鳳形式のログ(ファイルパス / 天鳳ログID / Tenhou URL / 天鳳JSON文字列)を解析する。"""
        if not self.available():
            raise EngineUnavailableError(
                f"mjai-reviewer が見つかりません (path={self.config.mjai_reviewer_path!r})。"
                " MJAI_REVIEWER_PATH と エンジン(Mortal重み/akochan)を設定してください。docs/SETUP.md 参照。"
            )
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "review.json"
            cmd = self._command_for(source, tmp, str(out_path))
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                raise EngineUnavailableError(
                    f"mjai-reviewer の実行に失敗しました (code={proc.returncode}).\n"
                    f"command: {' '.join(cmd)}\n"
                    f"stderr: {proc.stderr.strip()[:500]}\n"
                    "入力は天鳳形式である必要があります（雀魂は tensoul 等で変換）。"
                    " フラグが合わない場合は MJAI_REVIEWER_CMD で上書きできます。"
                )
            raw = out_path.read_text(encoding="utf-8") if out_path.exists() else proc.stdout
            data = json.loads(raw)
        return parse_and_enrich(data, self.actor)


# 後方互換のエイリアス（旧名）
MortalReviewer = MjaiReviewer
