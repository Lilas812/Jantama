"""雀魂(Mahjong Soul)の牌譜を入力源にする。

雀魂のログは protobuf + 認証が必要なため、取得・変換は外部ツール
（例: tensoul https://github.com/Equim-chan/tensoul）に委譲する。
変換ツールの実行ファイルを TENSOUL_PATH に、認証情報を MAJSOUL_ACCESS_TOKEN
に設定しておくと、URL から mjai イベント列を取得できる。

ツール未設定でも URL の解釈（paipu ID 抽出）は行えるため、Discord bot 側で
「ログファイルを添付してください」と案内する分岐に使える。
"""

from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path

from ..config import Config
from .base import PaifuSource, PaifuUnavailableError
from .local import LocalLogSource

# 例: https://game.mahjongsoul.com/?paipu=240101-xxxx-...._a123456
_PAIPU_RE = re.compile(r"paipu=([0-9A-Za-z\-]+)(?:_a(\d+))?")


def parse_paipu_url(url: str) -> tuple[str, str | None]:
    """雀魂の牌譜 URL から (paipu_id, account_suffix) を取り出す。

    URL でなく ID 直書きでも受理する。account 部 (_a...) は分離して返す。
    """
    m = _PAIPU_RE.search(url)
    if m:
        return m.group(1), m.group(2)
    # 既に ID の場合: 末尾 _a... を分離
    token = url.strip()
    if "_a" in token:
        base, _, acc = token.partition("_a")
        return base, acc or None
    return token, None


def is_majsoul_input(text: str) -> bool:
    """文字列が雀魂の牌譜 URL/ID らしいか。"""
    t = text.strip()
    return "mahjongsoul" in t or "maj-soul" in t or "paipu=" in t


class MahjongSoulSource:
    def __init__(self, url_or_id: str, config: Config | None = None) -> None:
        self.config = config or Config.from_env()
        self.paipu_id, self.account = parse_paipu_url(url_or_id)

    def converter_available(self) -> bool:
        if self.config.majsoul_fetch_cmd:  # コマンド上書き時は存在チェックを省く
            return True
        path = self.config.tensoul_path
        return bool(path) and shutil.which(path) is not None

    def build_command(self, out_path: str) -> list[str]:
        """変換ツールの起動コマンド。

        MAJSOUL_FETCH_CMD（{id}{out}{token} を置換）があればそれを使う。
        無ければ tensoul 想定の既定組み立て。
        """
        if self.config.majsoul_fetch_cmd:
            template = self.config.majsoul_fetch_cmd.format(
                id=self.paipu_id, out=out_path,
                token=self.config.majsoul_access_token or "",
            )
            return shlex.split(template)
        cmd = [self.config.tensoul_path, self.paipu_id, "--mjai", "-o", out_path]
        if self.config.majsoul_access_token:
            cmd += ["--token", self.config.majsoul_access_token]
        return cmd

    def load(self) -> list[dict]:
        if not self.converter_available():
            raise PaifuUnavailableError(
                "雀魂 URL からの取得には変換ツールが必要です。"
                " TENSOUL_PATH と MAJSOUL_ACCESS_TOKEN（または MAJSOUL_FETCH_CMD）を"
                " 設定するか、牌譜(mjai/ログ)ファイルを直接渡してください。"
                f" (paipu_id={self.paipu_id})"
            )
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "game.mjai.json"
            cmd = self.build_command(str(out_path))
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                raise PaifuUnavailableError(
                    f"牌譜変換に失敗しました (code={proc.returncode}).\n"
                    f"command: {' '.join(cmd)}\n"
                    f"stderr: {proc.stderr.strip()[:500]}\n"
                    "コマンドが合わない場合は MAJSOUL_FETCH_CMD で指定してください。"
                )
            if out_path.exists():
                return LocalLogSource(out_path).load()
            # 標準出力に出すツールにも対応
            return [json.loads(l) for l in proc.stdout.splitlines() if l.strip()]


def from_input(text: str, config: Config | None = None) -> PaifuSource:
    """入力文字列から適切な入力源を選ぶ。

    - 雀魂 URL / paipu ID  → MahjongSoulSource
    - 既存ファイルパス      → LocalLogSource
    """
    text = text.strip()
    if is_majsoul_input(text):
        return MahjongSoulSource(text, config)
    if Path(text).exists():
        return LocalLogSource(text)
    # 既定では雀魂 ID とみなす
    return MahjongSoulSource(text, config)
