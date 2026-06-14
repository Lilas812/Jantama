"""向聴数と受け入れ（ukeire）の計算。

`mahjong` ライブラリの向聴計算を土台に、受け入れ枚数を自前で算出する。
この「確定した数値」が、Claude が嘘をつかずに説明するための根拠になる。

注意: 副露（鳴き）がある手は本モジュールでは精密計算しない。鳴きの分だけ
必要な面子数が減るが本実装はそれを考慮しないため、副露時は available=False を返す。
"""

from __future__ import annotations

from mahjong.shanten import Shanten

from ..models import DecisionPoint, Metrics
from ..tiles import (
    index_to_tile,
    is_red_five,
    next_dora_index,
    normalize,
    tile_to_index,
    to_34_array,
)

_shanten = Shanten()


def calc_shanten(hand34: list[int]) -> int:
    """34 配列の手牌の向聴数。-1=和了, 0=聴牌, n=n向聴。"""
    return _shanten.calculate_shanten(list(hand34))


def calc_ukeire(
    hand34: list[int], visible34: list[int] | None = None
) -> tuple[int, dict[int, int]]:
    """13 枚（3n+1 枚）の手牌の受け入れを計算する。

    各牌種を 1 枚加えて向聴が下がるかを調べ、下がるなら「受け入れ」とし、
    場に見えていない残り枚数を数える。

    返り値: (受け入れ総枚数, {牌インデックス: 残り枚数})
    visible34 は手牌以外で見えている牌（ドラ表示・河・副露）のカウント。
    """
    base = calc_shanten(hand34)
    work = list(hand34)
    accepted: dict[int, int] = {}
    for i in range(34):
        in_hand = work[i]
        if in_hand >= 4:
            continue
        work[i] += 1
        if calc_shanten(work) < base:
            seen = visible34[i] if visible34 else 0
            remaining = 4 - in_hand - seen
            if remaining > 0:
                accepted[i] = remaining
        work[i] -= 1
    return sum(accepted.values()), accepted


def _count_dora(hand: list[str], dora_markers: list[str]) -> int:
    """手牌中のドラ枚数（表ドラ + 赤5）を数える。"""
    count = 0
    # 赤5
    count += sum(1 for p in hand if is_red_five(p))
    # 表ドラ: 表示牌の「次の牌」がドラ
    dora_indices = [next_dora_index(m) for m in dora_markers]
    hand34 = to_34_array(hand)
    for di in dora_indices:
        count += hand34[di]
    return count


def _discard_from(hand: list[str], discard: str) -> list[str]:
    """手牌から 1 枚を取り除いたリストを返す（赤の有無を考慮）。"""
    target = normalize(discard)
    out = list(hand)
    # まず厳密一致（赤も含めて）で除去を試みる
    for i, p in enumerate(out):
        if normalize(p) == target:
            del out[i]
            return out
    # 赤指定でない場合、同数牌（赤含む）を1枚除去
    ti = tile_to_index(target)
    for i, p in enumerate(out):
        if tile_to_index(p) == ti:
            del out[i]
            return out
    return out


def compute_metrics(dp: DecisionPoint) -> Metrics:
    """DecisionPoint から牌効率の数値を計算する。

    打牌判断（actual / recommended が単一の打牌）について、向聴と受け入れを出す。
    副露中の手は精密計算しないため available=False。
    """
    m = Metrics()
    m.dora_in_hand = _count_dora(dp.hand, dp.dora_markers)

    if dp.melds:
        m.available = False
        m.reason_unavailable = "副露があるため向聴・受け入れの精密計算は省略"
        return m

    hand34 = to_34_array(dp.hand)
    total = sum(hand34)
    # 打牌前の手牌は 3n+2 枚（ツモ後）であるべき
    if total % 3 != 2:
        m.available = False
        m.reason_unavailable = f"手牌枚数({total})が打牌前の形(3n+2)でない"
        return m

    m.shanten_before = calc_shanten(hand34)

    visible34 = _visible_excluding_hand(dp)

    def after(discard: str) -> tuple[int, int, list[str]]:
        remaining = _discard_from(dp.hand, discard)
        arr = to_34_array(remaining)
        sh = calc_shanten(arr)
        cnt, accepted = calc_ukeire(arr, visible34)
        tiles = [index_to_tile(i) for i in sorted(accepted)]
        return sh, cnt, tiles

    if _is_discard(dp.actual_action):
        sh, cnt, tiles = after(_discard_tile(dp.actual_action))
        m.shanten_after_actual = sh
        m.ukeire_after_actual = cnt
        m.ukeire_tiles_actual = tiles

    if dp.recommended_action and _is_discard(dp.recommended_action):
        sh, cnt, tiles = after(_discard_tile(dp.recommended_action))
        m.shanten_after_recommended = sh
        m.ukeire_after_recommended = cnt
        m.ukeire_tiles_recommended = tiles

    return m


def _visible_excluding_hand(dp: DecisionPoint) -> list[int]:
    """手牌以外で見えている牌のカウント（受け入れの残り枚数計算用）。"""
    visible = [0] * 34
    for marker in dp.dora_markers:
        visible[tile_to_index(marker)] += 1
    return visible


# ── 行動文字列の判定ヘルパ ────────────────────────────────────
# actual_action は "打牌 1p" / "1p" / "dahai:1p" など揺れがあるため緩く判定する。

def _is_discard(action: str) -> bool:
    return _discard_tile(action) is not None


def _discard_tile(action: str) -> str | None:
    """行動文字列から打牌の牌を取り出す。打牌でなければ None。"""
    if not action:
        return None
    tok = action.replace("打牌", "").replace("dahai", "").replace(":", " ").strip()
    tok = tok.split()[-1] if tok else ""
    try:
        tile_to_index(tok)
        return normalize(tok)
    except (ValueError, IndexError):
        return None
