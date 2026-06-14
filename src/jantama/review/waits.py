"""待ち推定（相手のテンパイの待ち牌を外側から読む）。

確定情報のみを根拠にする:
  - フリテン: リーチ者の河（＋立直後に場を通った牌）は待ちになり得ない。
  - スジ: 両面待ち {a,a+1} は待ち端のどちらかがフリテンなら不成立。
  - 壁(カベ): ある牌が4枚見えていれば、その牌を必要とする形（両面/カンチャン等）は
    作れない。3枚見えはワンチャンス（残り1枚のみ）で確率が低い。
  - 和了牌の残り枚数: 両面/カンチャン/ペンチャンは和了牌が残1枚以上必要。
    タンキは残2枚以上(1枚持ち＋和了1枚)、シャンポンは残3枚以上(2枚持ち＋和了1枚)。

各牌について成立し得る待ち形を求め、両面＞カンチャン/ペンチャン＞タンキ/シャンポン
の順で「待ちらしさ」を評価する。外側からの推定であり確定ではない点に注意。
"""

from __future__ import annotations

from ..tiles import index_to_tile, tile_to_jp, to_34_array

RYANMEN = "両面"
KANCHAN = "カンチャン"
PENCHAN = "ペンチャン"
TANKI = "タンキ"
SHANPON = "シャンポン"

# 待ちらしさの段階（危険度にも対応）: 0=待ちになり得ない / 1=タンキ・シャンポンのみ /
# 2=カンチャン・ペンチャン / 3=両面あり
_TIER_OF = {RYANMEN: 3, KANCHAN: 2, PENCHAN: 2, TANKI: 1, SHANPON: 1}


def seen_counts(ctx) -> list[int]:
    """自分から見えている牌の枚数（場の見え牌＋自分の手牌）。"""
    seen = to_34_array(ctx.visible_tiles)
    for i, c in enumerate(to_34_array(ctx.hand)):
        seen[i] += c
    return seen


def wait_shapes(ti: int, genbutsu: set[int], seen: list[int]) -> set[str]:
    """牌 ti が、現物集合 genbutsu を持つ相手の待ちになり得る形の集合。

    genbutsu はその相手に対する「待ちになり得ない牌index」（リーチなら河＋場を通った
    牌、黙テンならその家の河）。空集合が返れば ti はその相手に当たらない＝安全。
    """
    passed = genbutsu
    if ti in passed:  # フリテン/場を通った → 待ちでない
        return set()
    unseen_x = 4 - seen[ti]
    if unseen_x < 1:  # 和了牌が場に尽きている → 誰の待ちにもなり得ない
        return set()

    shapes: set[str] = set()
    if ti >= 27:  # 字牌は タンキ/シャンポン のみ
        if unseen_x >= 2:
            shapes.add(TANKI)
        if unseen_x >= 3:
            shapes.add(SHANPON)
        return shapes

    suit, v = ti // 9, ti % 9 + 1
    base = suit * 9

    def unseen_val(value: int) -> int:
        return (4 - seen[base + value - 1]) if 1 <= value <= 9 else 0

    def in_passed(value: int) -> bool:
        return 1 <= value <= 9 and (base + value - 1) in passed

    # 両面: 上側 {v+1,v+2}(待ち v と v+3) / 下側 {v-2,v-1}(待ち v-3 と v)
    # 真の両面は待ち両端が 1..9 に収まる必要がある（端だとペンチャン扱い）。
    # 反対端がフリテンなら成立しない（＝スジ）。
    if v <= 6 and unseen_val(v + 1) >= 1 and unseen_val(v + 2) >= 1 and not in_passed(v + 3):
        shapes.add(RYANMEN)
    if v >= 4 and unseen_val(v - 1) >= 1 and unseen_val(v - 2) >= 1 and not in_passed(v - 3):
        shapes.add(RYANMEN)
    # カンチャン {v-1,v+1}
    if 2 <= v <= 8 and unseen_val(v - 1) >= 1 and unseen_val(v + 1) >= 1:
        shapes.add(KANCHAN)
    # ペンチャン 3←{1,2} / 7←{8,9}
    if v == 3 and unseen_val(1) >= 1 and unseen_val(2) >= 1:
        shapes.add(PENCHAN)
    if v == 7 and unseen_val(8) >= 1 and unseen_val(9) >= 1:
        shapes.add(PENCHAN)
    # タンキ/シャンポン
    if unseen_x >= 2:
        shapes.add(TANKI)
    if unseen_x >= 3:
        shapes.add(SHANPON)
    return shapes


def wait_tier(ti: int, genbutsu: set[int], seen: list[int]) -> int:
    """牌 ti が、現物集合 genbutsu を持つ相手の待ちである「らしさ／危険度」(0-3)。"""
    shapes = wait_shapes(ti, genbutsu, seen)
    return max((_TIER_OF[s] for s in shapes), default=0)


def estimate_waits(genbutsu: set[int], seen: list[int]) -> dict[int, set[str]]:
    """現物 genbutsu を持つ相手の、待ちになり得る {牌index: 待ち形集合}（空集合は除く）。"""
    out: dict[int, set[str]] = {}
    for ti in range(34):
        shapes = wait_shapes(ti, genbutsu, seen)
        if shapes:
            out[ti] = shapes
    return out


_REL_JP = {1: "下家", 2: "対面", 3: "上家"}


def format_wait_note(ctx) -> str:
    """各脅威（リーチ＋黙テン濃厚）の待ち推定を文章化する（両面候補を中心に）。"""
    from .tenpai_read import list_threats  # 遅延 import（循環回避）

    threats = list_threats(ctx)
    if not threats:
        return ""
    seen = seen_counts(ctx)
    lines: list[str] = []
    for th in threats:
        waits = estimate_waits(th.genbutsu, seen)
        ryanmen = [ti for ti, s in waits.items() if RYANMEN in s]
        other = [ti for ti, s in waits.items() if RYANMEN not in s and (KANCHAN in s or PENCHAN in s)]
        kind = "リーチ" if th.kind == "riichi" else "黙テン濃厚"
        who = f"{_REL_JP.get((th.seat - ctx.actor) % 4, '他家')}({kind})"
        # 候補が広すぎる（=絞り込めない）ときは列挙せず広さだけ示す
        if not ryanmen:
            ryanmen_str = "なし（両面は否定済み）"
        elif len(ryanmen) > 12:
            ryanmen_str = f"広く{len(ryanmen)}種（絞り込み困難）"
        else:
            ryanmen_str = _tiles(ryanmen)
        other_str = _tiles(other) if other else "なし"
        lines.append(f"{who}: 両面待ち候補={ryanmen_str} / カンチャン等={other_str}")
    return "待ち推定（現物・スジ・壁で否定したもの以外。確定ではない）\n" + "\n".join(lines)


def _tiles(indices: list[int]) -> str:
    return "・".join(tile_to_jp(index_to_tile(i)) for i in sorted(indices))
