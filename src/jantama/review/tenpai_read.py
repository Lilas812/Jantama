"""黙テン（立直なしテンパイ）の気配推定と、脅威(リーチ＋黙テン)の統合。

立直は宣言があるので確定。黙テンは宣言が無いため、観測できる兆候から推定する:
  - 副露数: 2副露以上は速度を取った手でテンパイ寄り。
  - 連続ツモ切り: 中盤以降に数巡ツモ切りが続く家は手が固まっている＝テンパイ寄り。
  - 巡目: 終盤ほどテンパイ確率が上がる。

これらを粗く合算した確率がしきい値以上の家を「テンパイ濃厚」とみなし、リーチ者と
合わせて脅威(Threat)として扱う。黙テンの現物はその家自身の河（フリテン）で判定する。
あくまで外側からの推定であり確定ではない。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..tiles import tile_to_index

DAMATEN_THRESHOLD = 0.6   # これ以上で脅威として扱う（テンパイ濃厚）
DAMATEN_SIGNAL = 0.40     # これ以上で読み材料として表示（テンパイ気配）


@dataclass
class Threat:
    seat: int
    kind: str               # "riichi" | "damaten"
    confidence: float       # 0..1（リーチは 1.0）
    genbutsu: set[int]      # その家に対する現物（待ちになり得ない牌index）
    reasons: list[str] = field(default_factory=list)  # 黙テン推定の根拠


def _river_indices(ctx, seat: int) -> set[int]:
    river = ctx.rivers[seat] if seat < len(ctx.rivers) else []
    return {tile_to_index(p) for p, _ in river}


def consecutive_tsumogiri(ctx, seat: int) -> int:
    """河の末尾から連続するツモ切りの数。"""
    river = ctx.rivers[seat] if seat < len(ctx.rivers) else []
    n = 0
    for _, tg in reversed(river):
        if tg:
            n += 1
        else:
            break
    return n


def tenpai_probability(ctx, seat: int) -> tuple[float, list[str]]:
    """観測兆候から seat のテンパイ確率を粗く推定する（0..0.9、確定ではない）。"""
    reasons: list[str] = []
    junme = ctx.junme
    melds = ctx.meld_counts[seat] if seat < len(ctx.meld_counts) else 0
    tg = consecutive_tsumogiri(ctx, seat)

    base = max(0.0, min(0.45, (junme - 5) * 0.06))  # 巡目ベースライン
    if junme >= 12:
        reasons.append(f"終盤({junme}巡)")
    meld_bonus = {0: 0.0, 1: 0.10, 2: 0.28, 3: 0.42}.get(melds, 0.55)
    if melds >= 2:
        reasons.append(f"{melds}副露")
    tg_bonus = 0.0
    if tg >= 2:
        tg_bonus = {2: 0.12, 3: 0.28}.get(tg, 0.42)
        reasons.append(f"{tg}巡連続ツモ切り")

    prob = max(0.0, min(0.9, base + meld_bonus + tg_bonus))
    return prob, reasons


def list_threats(ctx, damaten_threshold: float = DAMATEN_THRESHOLD) -> list[Threat]:
    """脅威(リーチ確定＋黙テン濃厚)の一覧。danger/押し引きはこれを使う。"""
    threats: list[Threat] = []
    for r in ctx.riichi_opponents:
        threats.append(Threat(r, "riichi", 1.0, set(ctx.passed.get(r, set()))))
    reached = set(ctx.reached_seats)
    for seat in range(4):
        if seat == ctx.actor or seat in reached:
            continue
        prob, reasons = tenpai_probability(ctx, seat)
        if prob >= damaten_threshold:
            threats.append(Threat(seat, "damaten", prob, _river_indices(ctx, seat), reasons))
    return threats


_REL_JP = {1: "下家", 2: "対面", 3: "上家"}


def format_tenpai_signals(ctx) -> str:
    """テンパイ気配（リーチ以外で確率が一定以上の家）を文章化する。"""
    reached = set(ctx.reached_seats)
    lines: list[str] = []
    for seat in range(4):
        if seat == ctx.actor or seat in reached:
            continue
        prob, reasons = tenpai_probability(ctx, seat)
        if prob >= DAMATEN_SIGNAL and reasons:
            who = _REL_JP.get((seat - ctx.actor) % 4, "他家")
            level = "濃厚" if prob >= DAMATEN_THRESHOLD else "気配"
            lines.append(f"{who}: テンパイ{level}（{'・'.join(reasons)}）")
    if not lines:
        return ""
    return "黙テン気配（立直なし。推定）\n" + "\n".join(lines)
