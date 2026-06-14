"""押し引き（押す/降りる）の判断ロジック。

akochan/Mortal の EV に頼らず、自前で牌の危険度（現物・筋・無筋・字牌）を判定し、
テンパイ状況と併せて「押すか降りるか」を提案する。純粋な近似であり打点や複数リーチの
細かい評価まではしないが、根拠（現物・筋・向聴）を伴うコーチングができる。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..tiles import index_to_tile, tile_to_index, tile_to_jp, to_34_array

# 危険度 0=現物 / 1=筋・安全寄り / 2=無筋やや危険 / 3=無筋危険
_DANGER_LABEL = {0: "現物", 1: "筋(安全寄り)", 2: "無筋(やや危険)", 3: "無筋(危険)"}
_REL_JP = {1: "下家", 2: "対面", 3: "上家"}


def _suji_values(ctx, seat: int) -> dict[int, set[int]]:
    """リーチ者 seat の河から、スート別に切られた数牌の値の集合を返す（筋判定用）。"""
    by_suit: dict[int, set[int]] = {0: set(), 1: set(), 2: set()}
    river = ctx.rivers[seat] if seat < len(ctx.rivers) else []
    for pai, _ in river:
        ti = tile_to_index(pai)
        if ti < 27:
            by_suit[ti // 9].add(ti % 9 + 1)
    return by_suit


def _is_suji(value: int, river_vals: set[int]) -> bool:
    """両面待ちに対する筋か（端は片筋、4-6は中筋＝両側必要）。"""
    if value in (1, 2, 3):
        return (value + 3) in river_vals
    if value in (7, 8, 9):
        return (value - 3) in river_vals
    return (value - 3) in river_vals and (value + 3) in river_vals


def _danger_vs(ti: int, seat: int, ctx, seen: list[int]) -> int:
    """牌 ti のリーチ者 seat に対する危険度（0-3）。現物判定は呼び出し側で済ませる前提。"""
    if ti >= 27:  # 字牌: 残り枚数で判定（残2でシャンポン、残3+は生牌で危険）
        remaining = 4 - seen[ti]
        if remaining <= 1:
            return 1
        return 2 if remaining == 2 else 3
    suit, value = ti // 9, ti % 9 + 1
    if _is_suji(value, _suji_values(ctx, seat)[suit]):
        return 1
    return 2 if value in (1, 9) else 3  # 端の無筋はやや、中張の無筋は危険


def tile_danger(ti: int, ctx, seen: list[int]) -> tuple[int, str]:
    """全リーチ者に対する牌 ti の危険度（最も危険な相手に合わせる）。"""
    if not ctx.riichi_opponents:
        return 0, _DANGER_LABEL[0]
    worst = 0
    for r in ctx.riichi_opponents:
        if ti in ctx.passed.get(r, set()):
            tier = 0  # この相手には現物
        else:
            tier = _danger_vs(ti, r, ctx, seen)
        worst = max(worst, tier)
    return worst, _DANGER_LABEL[worst]


@dataclass
class PushFold:
    recommended_idx: int
    is_mistake: bool
    note: str


def analyze_push_fold(ctx, hand34: list[int], evals: dict[int, tuple[int, int]],
                      best_idx: int, actual_idx: int, dora_in_hand: int,
                      min_ukeire_drop: int) -> PushFold | None:
    """リーチがある局面での押し引き判断。リーチが無ければ None。"""
    if not ctx.riichi_opponents:
        return None
    seen = to_34_array(ctx.visible_tiles)
    for i in range(34):
        seen[i] += hand34[i]

    def danger(ti: int) -> int:
        return tile_danger(ti, ctx, seen)[0]

    best_sh, best_uk = evals[best_idx]
    actual_sh, actual_uk = evals.get(actual_idx, evals[best_idx])
    my_tenpai = best_sh == 0
    actual_d = danger(actual_idx)
    # 最も安全な打牌（同点なら受け入れ最大を残す）
    safest_idx = min(evals, key=lambda i: (danger(i), -evals[i][1]))

    if my_tenpai:
        rec, flag = best_idx, "push"
        is_mistake = actual_sh > best_sh or (
            actual_sh == best_sh and best_uk - actual_uk >= min_ukeire_drop
        )
        # テンパイでも、安全牌でのベタ降りを選んでいるなら咎めない
        if is_mistake and actual_d == 0 and danger(best_idx) >= 2:
            rec, is_mistake, flag = actual_idx, False, "fold_ok"
    else:
        if actual_d >= 2:  # 非テンパイでリーチに危険牌を押している → 降り推奨
            rec, is_mistake, flag = safest_idx, actual_idx != safest_idx, "fold"
        else:  # 既に安全寄り → 現状維持（咎めない）
            rec, is_mistake, flag = actual_idx, False, "fold_ok"

    note = _format_note(ctx, seen, danger, actual_idx, rec, safest_idx,
                        best_sh, my_tenpai, flag, dora_in_hand)
    return PushFold(rec, is_mistake, note)


def _format_note(ctx, seen, danger, actual_idx, rec_idx, safest_idx,
                 best_sh, my_tenpai, flag, dora) -> str:
    who = "・".join(_REL_JP.get((s - ctx.actor) % 4, "他家") for s in ctx.riichi_opponents)
    a_jp = tile_to_jp(index_to_tile(actual_idx))
    a_d = _DANGER_LABEL[danger(actual_idx)]
    shanten = "テンパイ" if my_tenpai else f"{best_sh}向聴"
    head = f"他家リーチ（{who}）。あなたは{shanten}。打{a_jp}＝{a_d}。"
    if flag == "push":
        tail = f"テンパイなので押し優先（手の中のドラ{dora}）。"
        if danger(rec_idx) >= 2:
            tail += f"ただし推奨の打{tile_to_jp(index_to_tile(rec_idx))}は無筋でリスクあり。"
    elif flag == "fold":
        s_jp = tile_to_jp(index_to_tile(safest_idx))
        s_d = _DANGER_LABEL[danger(safest_idx)]
        tail = f"未テンパイで無筋を押すのは損。ここは降り推奨——最も安全な打{s_jp}（{s_d}）へ。"
    else:  # fold_ok
        tail = "安全牌での撤退は妥当。無理に押さないのが良い。"
    return head + tail
