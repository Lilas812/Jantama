"""Claude へ渡すプロンプトの組み立て。

設計の肝: 牌譜をそのまま投げて説明させると麻雀の事実を捏造する。よって
向聴・受け入れ・ドラ・期待値といった「計算済みの確定値」だけを根拠として渡し、
モデルにはその数値の意味づけ（なぜその打牌が良いのか）に専念させる。
"""

from __future__ import annotations

from ..models import DecisionPoint, Metrics
from ..tiles import dora_tiles, hand_to_jp, tile_to_jp

SYSTEM_PROMPT = """\
あなたは雀魂(じゃんたま)の対局を指導する麻雀コーチです。
解析エンジンが算出した「推奨打牌」と各種の数値を渡すので、
「なぜその打牌が良いのか / プレイヤーの選択は何が違ったのか」を日本語で説明してください。

厳守事項:
- 説明は、与えられた数値（向聴数・受け入れ枚数・受け入れ牌・ドラ・期待値など）だけを根拠にすること。
- 与えられていない牌の枚数・点数・確率を新たに創作しないこと。数値が無い項目は断定しない。
- 中級者にも分かる平易な言葉で。専門用語(向聴・受け入れ等)は軽く補足する。
- 2〜4文程度に簡潔に。前置きや挨拶は不要。結論(どちらが良いか)から書く。
- プレイヤーの選択が推奨と同じ場合は、その選択がなぜ妥当かを述べる。
"""


def _fmt_tiles(tiles: list[str]) -> str:
    if not tiles:
        return "なし"
    return "・".join(tile_to_jp(t) for t in tiles)


def _shanten_jp(value: int | None) -> str:
    if value is None:
        return "不明"
    if value == -1:
        return "和了"
    if value == 0:
        return "聴牌(テンパイ)"
    return f"{value}向聴"


def build_user_prompt(dp: DecisionPoint, metrics: Metrics) -> str:
    """1 局面分の根拠データを Claude 用のテキストに整形する。"""
    lines: list[str] = []
    seat = "親" if dp.is_dealer else "子"
    lines.append(
        f"# 局面\n{dp.round_wind}{dp.kyoku}局 {dp.honba}本場 / "
        f"自風={dp.seat_wind}({seat}) / {dp.junme}巡目"
    )

    dora = dora_tiles(dp.dora_markers)
    lines.append(
        "## 場\n"
        f"ドラ表示: {_fmt_tiles(dp.dora_markers)} → ドラ: {_fmt_tiles(dora)}"
    )
    if dp.scores:
        lines.append(f"点棒: {dp.scores}")

    tsumo = f"（ツモ: {tile_to_jp(dp.drawn_tile)}）" if dp.drawn_tile else ""
    lines.append(
        "## 手牌\n"
        f"{hand_to_jp(dp.hand)} {tsumo}\n"
        f"手牌中のドラ: {metrics.dora_in_hand}枚"
    )
    if dp.melds:
        lines.append(f"副露: {', '.join(dp.melds)}")

    lines.append("## 数値")
    if metrics.available:
        lines.append(f"打牌前: {_shanten_jp(metrics.shanten_before)}")
        lines.append(
            f"あなたの選択: {_fmt_action(dp.actual_action)} → "
            f"{_shanten_jp(metrics.shanten_after_actual)} / "
            f"受け入れ {_count(metrics.ukeire_after_actual)}"
            f"（{_fmt_tiles(metrics.ukeire_tiles_actual)}）"
        )
        if dp.recommended_action:
            lines.append(
                f"エンジン推奨: {_fmt_action(dp.recommended_action)} → "
                f"{_shanten_jp(metrics.shanten_after_recommended)} / "
                f"受け入れ {_count(metrics.ukeire_after_recommended)}"
                f"（{_fmt_tiles(metrics.ukeire_tiles_recommended)}）"
            )
    else:
        lines.append(f"（牌効率の精密計算は省略: {metrics.reason_unavailable}）")
        lines.append(f"あなたの選択: {_fmt_action(dp.actual_action)}")
        if dp.recommended_action:
            lines.append(f"エンジン推奨: {_fmt_action(dp.recommended_action)}")

    # エンジンの評価値
    ev_lines = []
    if dp.recommended_ev is not None:
        ev_lines.append(f"推奨の評価値={dp.recommended_ev:.3f}")
    if dp.actual_ev is not None:
        ev_lines.append(f"実際の評価値={dp.actual_ev:.3f}")
    if dp.ev_gap is not None:
        ev_lines.append(f"差={dp.ev_gap:.3f}")
    if ev_lines:
        lines.append("## エンジン評価\n" + " / ".join(ev_lines))

    if dp.candidates:
        top = sorted(dp.candidates, key=lambda c: c[1], reverse=True)[:5]
        cand = "、".join(f"{_fmt_action(a)}({v:.3f})" for a, v in top)
        lines.append(f"候補上位: {cand}")

    lines.append(
        "\n# 指示\n上の数値だけを根拠に、推奨打牌の方が良い理由"
        "（または、あなたの選択でも妥当な理由）を日本語で簡潔に説明してください。"
    )
    return "\n".join(lines)


def _fmt_action(action: str) -> str:
    """行動ラベルを表示用に。打牌牌なら日本語牌名にする。"""
    if not action:
        return "不明"
    try:
        return f"打 {tile_to_jp(action)}"
    except (ValueError, IndexError):
        return action


def _count(value: int | None) -> str:
    return "不明" if value is None else f"{value}枚"
