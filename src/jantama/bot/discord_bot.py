"""じゃん玉 Discord bot。

使い方:
  - スラッシュコマンド  /kaisetsu url:<雀魂の牌譜URL> [actor:0-3]
  - もしくは bot にメンションしつつ 牌譜URL を貼る / mjai ログ(.json/.jsonl)を添付する

重い処理（エンジン解析 + Claude 呼び出し）は別スレッドで実行し、
結果は 2000 文字制限に合わせて分割送信する。
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import discord

from ..config import Config
from ..models import Explanation
from ..pipeline import analyze
from ..sources import LocalLogSource, is_majsoul_input
from ..sources.mahjong_soul import _PAIPU_RE  # noqa: PLC2701 — URL 検出に再利用

DISCORD_LIMIT = 2000
_SEVERITY_TAG = {"major": "🔴 大きな損", "minor": "🟡 小さな損", "info": "🟢 参考"}


def format_explanations(explanations: list[Explanation]) -> list[str]:
    """説明を Discord 送信用のメッセージ群（各 2000 文字以内）に整形する。"""
    blocks: list[str] = []
    for i, exp in enumerate(explanations, 1):
        tag = _SEVERITY_TAG.get(exp.severity, exp.severity)
        d = exp.decision
        block = (
            f"**{i}. {exp.header()}** [{tag}]\n"
            f"あなた: `{d.actual_action}` / 推奨: `{d.recommended_action}`\n"
            f"{exp.text}"
        )
        blocks.append(block)
    return _chunk(blocks)


def _chunk(blocks: list[str]) -> list[str]:
    """ブロック群を 2000 文字以内のメッセージにまとめる。"""
    messages: list[str] = []
    current = ""
    for block in blocks:
        # 単体で長すぎるブロックは強制分割
        while len(block) > DISCORD_LIMIT:
            head, block = block[: DISCORD_LIMIT - 1], block[DISCORD_LIMIT - 1 :]
            if current:
                messages.append(current)
                current = ""
            messages.append(head)
        if not current:
            current = block
        elif len(current) + len(block) + 2 <= DISCORD_LIMIT:
            current += "\n\n" + block
        else:
            messages.append(current)
            current = block
    if current:
        messages.append(current)
    return messages or ["説明すべき局面は見つかりませんでした。"]


class JantamaBot(discord.Client):
    def __init__(self, config: Config) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.config = config
        self.tree = discord.app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        self._register_commands()
        await self.tree.sync()

    def _register_commands(self) -> None:
        @self.tree.command(
            name="kaisetsu", description="雀魂の牌譜を解析して打牌の理由を説明します"
        )
        @discord.app_commands.describe(
            url="雀魂の牌譜URL または paipu ID", actor="解析するプレイヤー(0-3)"
        )
        async def kaisetsu(interaction: discord.Interaction, url: str, actor: int = 0):
            await interaction.response.defer(thinking=True)
            try:
                explanations = await asyncio.to_thread(
                    analyze, url, config=self.config, actor=actor
                )
            except Exception as exc:  # noqa: BLE001
                await interaction.followup.send(f"エラー: {exc}")
                return
            for msg in format_explanations(explanations):
                await interaction.followup.send(msg)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        is_dm = message.guild is None
        mentioned = self.user in message.mentions if self.user else False
        if not (is_dm or mentioned):
            return

        # 添付された mjai ログを優先
        log_attachment = next(
            (a for a in message.attachments if a.filename.endswith((".json", ".jsonl"))),
            None,
        )
        try:
            if log_attachment is not None:
                explanations = await self._analyze_attachment(log_attachment)
            elif is_majsoul_input(message.content) or _PAIPU_RE.search(message.content):
                explanations = await asyncio.to_thread(
                    analyze, message.content, config=self.config
                )
            else:
                await message.reply(
                    "雀魂の牌譜URLを貼るか、mjaiログ(.json/.jsonl)を添付してください。"
                    " 使い方: `/kaisetsu`"
                )
                return
        except Exception as exc:  # noqa: BLE001
            await message.reply(f"エラー: {exc}")
            return

        for msg in format_explanations(explanations):
            await message.reply(msg)

    async def _analyze_attachment(self, attachment: discord.Attachment) -> list[Explanation]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / attachment.filename
            await attachment.save(path)
            return await asyncio.to_thread(
                analyze, LocalLogSource(path), config=self.config
            )


def run(config: Config | None = None) -> None:
    config = config or Config.from_env()
    if not config.discord_bot_token:
        raise SystemExit("DISCORD_BOT_TOKEN が未設定です。.env を確認してください。")
    JantamaBot(config).run(config.discord_bot_token)


if __name__ == "__main__":
    run()
