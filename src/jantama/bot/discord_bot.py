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
from ..models import GameReport
from ..pipeline import analyze_report
from ..sources import LocalLogSource, is_majsoul_input
from ..sources.mahjong_soul import _PAIPU_RE  # noqa: PLC2701 — URL 検出に再利用

_SEVERITY_TAG = {"major": "🔴 大きな損", "minor": "🟡 小さな損", "info": "🟢 参考"}
_FIELD_LIMIT = 1024
_DESC_LIMIT = 4096
_FIELDS_PER_EMBED = 10


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _report_color(report: GameReport):
    if any(e.severity == "major" for e in report.explanations):
        return discord.Color.red()
    if any(e.severity == "minor" for e in report.explanations):
        return discord.Color.gold()
    return discord.Color.green()


def build_embeds(report: GameReport) -> list[discord.Embed]:
    """解析レポートを Discord の Embed 群に整形する（総評 + 個別指摘）。"""
    s = report.stats
    color = _report_color(report)
    title = f"📊 解析 {s.total_decisions}局面 / ミス {s.mistakes}件"
    if s.match_rate is not None:
        title += f" / 推奨一致率 {s.match_rate * 100:.0f}%"
    summary = _truncate(report.summary or "（総評なし）", _DESC_LIMIT)
    embeds = [discord.Embed(title=_truncate(title, 256), description=summary, color=color)]

    field_embed: discord.Embed | None = None
    for i, exp in enumerate(report.explanations, 1):
        if field_embed is None or len(field_embed.fields) >= _FIELDS_PER_EMBED:
            field_embed = discord.Embed(title="🀄 指摘", color=color)
            embeds.append(field_embed)
        tag = _SEVERITY_TAG.get(exp.severity, exp.severity)
        d = exp.decision
        name = _truncate(f"{i}. {exp.header()} [{tag}]", 256)
        value = _truncate(
            f"あなた: `{d.actual_action}` / 推奨: `{d.recommended_action}`\n{exp.text}",
            _FIELD_LIMIT,
        )
        field_embed.add_field(name=name, value=value, inline=False)
    return embeds


def _embed_batches(embeds: list[discord.Embed], size: int = 10) -> list[list[discord.Embed]]:
    """Discord は 1 メッセージあたり最大 10 Embed。"""
    return [embeds[i : i + size] for i in range(0, len(embeds), size)] or [[]]


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
                report = await asyncio.to_thread(
                    analyze_report, url, config=self.config, actor=actor
                )
            except Exception as exc:  # noqa: BLE001
                await interaction.followup.send(f"エラー: {exc}")
                return
            for batch in _embed_batches(build_embeds(report)):
                await interaction.followup.send(embeds=batch)

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
                report = await self._analyze_attachment(log_attachment)
            elif is_majsoul_input(message.content) or _PAIPU_RE.search(message.content):
                report = await asyncio.to_thread(
                    analyze_report, message.content, config=self.config
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

        batches = _embed_batches(build_embeds(report))
        await message.reply(embeds=batches[0])
        for batch in batches[1:]:
            await message.channel.send(embeds=batch)

    async def _analyze_attachment(self, attachment: discord.Attachment) -> GameReport:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / attachment.filename
            await attachment.save(path)
            return await asyncio.to_thread(
                analyze_report, LocalLogSource(path), config=self.config
            )


def run(config: Config | None = None) -> None:
    config = config or Config.from_env()
    if not config.discord_bot_token:
        raise SystemExit("DISCORD_BOT_TOKEN が未設定です。.env を確認してください。")
    JantamaBot(config).run(config.discord_bot_token)


if __name__ == "__main__":
    run()
