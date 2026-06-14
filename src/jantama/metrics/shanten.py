"""向聴数と受け入れ（ukeire）の計算。

`mahjong` ライブラリの向聴計算を土台に、受け入れ枚数を自前で算出する。
この「確定した数値」が、Claude が嘘をつかずに説明するための根拠になる。

副露（鳴き）がある手も計算できる。`mahjong` の向聴計算は概要牌の枚数ベースで、
11/8/5 枚なら鳴き 1/2/3 の手として必要面子数を自動調整するため、概要牌をそのまま
渡せばよい。ただし開いた手では七対子・国士は成立しないので、それらは除外する。
（副露牌の中のドラは meld の構造情報が無いため未集計。EV はエンジン側が考慮する。）
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
    without_tile,
)

_shanten = Shanten()


def calc_shanten(hand34: list[int], allow_special: bool = True) -> int:
    """34 配列の手牌の向聴数。-1=和了, 0=聴牌, n=n向聴。

    `mahjong` の向聴計算は枚数ベースで、概要牌が 11/8/5 枚なら鳴き(1/2/3)の手として
    必要面子数を自動調整する。`allow_special=False` で七対子・国士を除外する
    （副露している＝開いた手では七対子・国士は成立しないため）。
    """
    return _shanten.calculate_shanten(
        list(hand34),
        use_chiitoitsu=allow_special,
        use_kokushi=allow_special,
    )


def calc_ukeire(
    hand34: list[int],
    visible34: list[int] | None = None,
    allow_special: bool = True,
) -> tuple[int, dict[int, int]]:
    """13 枚（3n+1 枚）の手牌の受け入れを計算する。

    各牌種を 1 枚加えて向聴が下がるかを調べ、下がるなら「受け入れ」とし、
    場に見えていない残り枚数を数える。鳴き手は allow_special=False を渡すこと。

    返り値: (受け入れ総枚数, {牌インデックス: 残り枚数})
    visible34 は手牌以外で見えている牌（ドラ表示・河・副露）のカウント。
    """
    base = calc_shanten(hand34, allow_special)
    work = list(hand34)
    accepted: dict[int, int] = {}
    for i in range(34):
        in_hand = work[i]
        if in_hand >= 4:
            continue
        work[i] += 1
        if calc_shanten(work, allow_special) < base:
            seen = visible34[i] if visible34 else 0
            remaining = 4 - in_hand - seen
            if remaining > 0:
                accepted[i] = remaining
        work[i] -= 1
    return sum(accepted.values()), accepted


def _count_dora(
    hand: list[str], dora_markers: list[str], meld_tiles: list[str] | None = None
) -> int:
    """ドラ枚数（表ドラ + 赤5）を数える。meld_tiles を渡すと副露牌も含める。"""
    tiles = list(hand) + list(meld_tiles or [])
    # 赤5
    count = sum(1 for p in tiles if is_red_five(p))
    # 表ドラ: 表示牌の「次の牌」がドラ
    dora_indices = [next_dora_index(m) for m in dora_markers]
    arr = to_34_array(tiles)
    for di in dora_indices:
        count += arr[di]
    return count


def _discard_from(hand: list[str], discard: str) -> list[str]:
    """手牌から 1 枚を取り除いたリストを返す（赤の有無を考慮）。"""
    return without_tile(hand, discard)


def compute_metrics(dp: DecisionPoint) -> Metrics:
    """DecisionPoint から牌効率の数値を計算する。

    打牌判断（actual / recommended が単一の打牌）について、向聴と受け入れを出す。
    副露中の手は精密計算しないため available=False。
    """
    m = Metrics()
    # 概要牌 + 副露牌(あれば)のドラを数える。meld_tiles が無ければ概要牌のみ。
    m.dora_in_hand = _count_dora(dp.hand, dp.dora_markers, dp.meld_tiles)

    hand34 = to_34_array(dp.hand)
    total = sum(hand34)
    # 打牌前(ツモ後)の概要牌は 3n+2 枚。鳴き m 回なら 14-3m 枚 = 14/11/8/5/2。
    if total % 3 != 2 or not (2 <= total <= 14):
        m.available = False
        m.reason_unavailable = f"手牌枚数({total})が打牌前の形(3n+2)でない"
        return m

    # 概要牌の枚数から鳴き回数を導く（牌譜の melds 情報が無くても判定可能）。
    m.num_melds = (14 - total) // 3
    open_hand = m.num_melds > 0 or bool(dp.melds)
    allow_special = not open_hand  # 副露中は七対子・国士を除外

    m.shanten_before = calc_shanten(hand34, allow_special)

    # 場に見えている牌（河・副露・ドラ表示）。無ければドラ表示のみで近似。
    base_visible = (
        to_34_array(dp.visible_tiles) if dp.visible_tiles else _visible_excluding_hand(dp)
    )

    def after(discard: str) -> tuple[int, int, list[str]]:
        remaining = _discard_from(dp.hand, discard)
        arr = to_34_array(remaining)
        sh = calc_shanten(arr, allow_special)
        visible = list(base_visible)
        visible[tile_to_index(discard)] += 1  # 切った牌も場に出た1枚として残り枚数から控除
        cnt, accepted = calc_ukeire(arr, visible, allow_special)
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
