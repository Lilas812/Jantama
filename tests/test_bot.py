"""Discord Embed 整形のテスト（bot 起動不要）。"""

import discord

from jantama.bot.discord_bot import _embed_batches, build_embeds
from jantama.models import DecisionPoint, Explanation, GameReport, Metrics, ReviewStats


def _dp() -> DecisionPoint:
    return DecisionPoint(
        round_wind="東", kyoku=1, honba=0, seat=0, seat_wind="東", is_dealer=True,
        junme=3, hand=[], drawn_tile=None, dora_markers=[],
        actual_action="1m", recommended_action="E",
    )


def _exp(severity: str, text: str = "説明") -> Explanation:
    return Explanation(decision=_dp(), metrics=Metrics(), text=text, severity=severity)


def test_summary_embed_has_stats_and_summary():
    report = GameReport(
        stats=ReviewStats(total_decisions=10, mistakes=2, total_ev_loss=3.1),
        explanations=[_exp("major"), _exp("minor")],
        summary="全体的に手なりが多めです。",
    )
    embeds = build_embeds(report)
    head = embeds[0]
    assert "10局面" in head.title
    assert "ミス 2件" in head.title
    assert "一致率 80%" in head.title
    assert head.description == "全体的に手なりが多めです。"
    assert head.color == discord.Color.red()  # major があるので赤
    assert sum(len(e.fields) for e in embeds[1:]) == 2


def test_long_text_is_truncated_to_field_limit():
    report = GameReport(
        stats=ReviewStats(total_decisions=1, mistakes=1),
        explanations=[_exp("major", "あ" * 2000)],
        summary="s",
    )
    field = build_embeds(report)[1].fields[0]
    assert len(field.value) <= 1024


def test_findings_split_across_embeds():
    report = GameReport(
        stats=ReviewStats(total_decisions=30, mistakes=23),
        explanations=[_exp("minor") for _ in range(23)],
        summary="s",
    )
    embeds = build_embeds(report)
    # 総評1 + 指摘embed3(10,10,3) = 4
    assert len(embeds) == 4
    assert all(len(b) <= 10 for b in _embed_batches(embeds))


def test_green_color_and_single_embed_when_no_findings():
    report = GameReport(
        stats=ReviewStats(total_decisions=5, mistakes=0), explanations=[], summary="good"
    )
    embeds = build_embeds(report)
    assert len(embeds) == 1
    assert embeds[0].color == discord.Color.green()
