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
- 結論(どちらが良いか)から書く。前置きや挨拶は不要。
- 抽象論で終えず、具体的な牌名・待ち・受け入れ牌に触れる（例:「8索切りで1索4索の8枚待ち」）。
- 「押し引き」情報がある場合は、安全度と効率の両面から触れる（他家リーチ時に現物で
  ベタ降りしているなら、それが妥当かを評価する）。
- 「河」に手出し情報（*=手出し）がある場合、相手の手の進み・聴牌気配の読みに活用してよい
  （例: 中盤以降に手出しが続く家は手が進んでいる可能性）。ただし数値の無い推測は断定しない。
- 「待ち推定」がある場合、両面候補の牌は危険、否定された牌（現物・スジ・壁）は安全、という
  読みに使ってよい。ただしこれは外側からの推定であり、相手の待ちは確定ではないと明示する。
- 「黙テン気配」がある場合、立直していなくてもテンパイの可能性として押し引きに反映してよい
  （副露数・連続ツモ切り・巡目が根拠）。これも推定であり確定ではない。
- 説明の長さは損失(EV差・向聴差)の大きさに合わせる。大きい時は理由と「次の指針」まで丁寧に(3〜4文)、
  小さい時は要点だけ簡潔に(1〜2文)。
- プレイヤーの選択が推奨と同じ場合は、その選択がなぜ妥当かを一言で述べる。
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
    if dp.river_note:
        lines.append(dp.river_note)
    if dp.tenpai_note:
        lines.append(dp.tenpai_note)

    tsumo = f"（ツモ: {tile_to_jp(dp.drawn_tile)}）" if dp.drawn_tile else ""
    open_hand = metrics.num_melds > 0 or bool(dp.melds)
    if not open_hand:
        dora_label = "手牌中のドラ"
    elif dp.meld_tiles:
        dora_label = "ドラ（手牌＋副露）"  # 副露牌も集計済み
    else:
        dora_label = "手牌中のドラ（副露除く）"
    lines.append(
        "## 手牌\n"
        f"{hand_to_jp(dp.hand)} {tsumo}\n"
        f"{dora_label}: {metrics.dora_in_hand}枚"
    )
    if dp.melds:
        lines.append(f"副露: {', '.join(_fmt_meld(x) for x in dp.melds)}")
    elif metrics.num_melds:
        lines.append(f"副露: {metrics.num_melds}つ（詳細不明）")

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

    if dp.safety_note:
        lines.append(f"## 押し引き\n{dp.safety_note}")
    if dp.wait_note:
        lines.append(f"## {dp.wait_note}")

    if dp.note:
        lines.append(f"## 補足\n{dp.note}")

    lines.append(
        "\n# 指示\n上の数値だけを根拠に、推奨打牌の方が良い理由"
        "（または、あなたの選択でも妥当な理由）を日本語で簡潔に説明してください。"
    )
    return "\n".join(lines)


_MELD_JP = {
    "pon": "ポン", "chi": "チー", "kan": "カン", "ankan": "暗槓",
    "minkan": "明槓", "daiminkan": "大明槓", "kakan": "加槓",
}


def _fmt_meld(meld: object) -> str:
    """副露(mjai の dict または文字列)を短い日本語ラベルにする。"""
    if isinstance(meld, dict):
        label = _MELD_JP.get(str(meld.get("type", "")), str(meld.get("type", "副露")))
        pai = meld.get("pai", "")
        try:
            pai = tile_to_jp(pai) if pai else ""
        except (ValueError, IndexError):
            pass
        return f"{label} {pai}".strip()
    return str(meld)


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


# ── 対局全体のサマリ ──────────────────────────────────────────

SUMMARY_SYSTEM_PROMPT = """\
あなたは雀魂(じゃんたま)の対局を講評する麻雀コーチです。
牌譜全体の集計と、個別に検出した要改善点の一覧を渡すので、プレイヤーへの総評をまとめてください。

厳守事項:
- 与えられた数値・指摘だけを根拠にすること。新たな事実・牌・点数を創作しない。
- まず全体の傾向(良かった点 / 課題)を1〜2文で述べる。
- 次に「次に意識すべきこと」を2〜3個の箇条書きで示す。次の対局で実行できる具体的な粒度にする。
- 最も損失の大きいパターン（EV差や向聴差が大きいもの）を優先して扱う。
- 中級者にも分かる平易な言葉で、前向きな口調。断定的に決めつけない。挨拶や前置きは不要。
- 指摘が無い場合は、推奨と高い一致率である旨を簡潔に評価する。
"""


def build_summary_prompt(stats, explanations: list) -> str:
    """集計と個別指摘から、総評用のプロンプトを組み立てる。"""
    lines: list[str] = ["# 対局全体の集計"]
    lines.append(f"解析した意思決定: {stats.total_decisions} 局面 / 推奨と異なった: {stats.mistakes} 回")
    if stats.match_rate is not None:
        lines.append(f"推奨一致率: {stats.match_rate * 100:.1f}%")
    if stats.total_ev_loss is not None:
        lines.append(f"検出したミスの EV 損失合計: {stats.total_ev_loss:.2f}")

    major = sum(1 for e in explanations if e.severity == "major")
    minor = sum(1 for e in explanations if e.severity == "minor")
    lines.append(f"指摘の内訳: 大きな損 {major} 件 / 小さな損 {minor} 件")

    if explanations:
        lines.append("\n# 個別の指摘（要約）")
        for e in explanations:
            d = e.decision
            gap = f" / EV差 {d.ev_gap:.2f}" if d.ev_gap is not None else ""
            shift = ""
            m = e.metrics
            if (
                m.shanten_after_actual is not None
                and m.shanten_after_recommended is not None
                and m.shanten_after_actual != m.shanten_after_recommended
            ):
                shift = f" / 向聴 {m.shanten_after_actual}→{m.shanten_after_recommended}"
            lines.append(
                f"- {d.round_wind}{d.kyoku}局{d.junme}巡目: "
                f"{_fmt_action(d.actual_action)}（推奨 {_fmt_action(d.recommended_action)}）{gap}{shift}"
            )

    lines.append(
        "\n# 指示\n上の数値・指摘だけを根拠に、(1)全体の傾向を1〜2文、"
        "(2)次に意識すべき改善点を2〜3個の箇条書きで、麻雀コーチとして簡潔にまとめてください。"
    )
    return "\n".join(lines)
