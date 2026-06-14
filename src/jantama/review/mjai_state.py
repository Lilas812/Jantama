"""mjai ゲームログを走査し、各打牌局面の盤面状態を復元する共通モジュール。

牌効率エンジンや Mortal 経路の補完など、複数箇所で同じ状態復元を使えるよう
切り出している。手牌・副露・ドラ・場に見えている牌に加え、**立直と現物(安全牌)**
も追跡するので、押し引きの判断材料を局面ごとに得られる。

立直後の自分の強制ツモ切りは意思決定ではないため、対象プレイヤーのその打牌は
yield しない（宣言打牌は yield する）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

from ..tiles import tile_to_index, without_tile

_BAKAZE = {"E": "東", "S": "南", "W": "西", "N": "北"}
_JIKAZE = ["東", "南", "西", "北"]
_FURO_LABEL = {
    "pon": "ポン", "chi": "チー", "daiminkan": "大明槓",
    "ankan": "暗槓", "kakan": "加槓",
}


@dataclass
class DecisionContext:
    """ある打牌局面（対象プレイヤーが捨てる直前）の盤面。"""

    bakaze: str
    kyoku: int
    honba: int
    oya: int
    scores: list[int] | None
    actor: int
    seat_wind: str
    is_dealer: bool
    junme: int
    hand: list[str]              # 概要牌（ツモ含む。3n+2）
    drawn: str | None
    discard: str                 # 実際に切った牌（正規化前の mjai 牌）
    dora_markers: list[str]
    meld_descs: list[str]
    meld_tiles: list[str]
    visible_tiles: list[str]     # 河 + 副露 + ドラ表示（自分の手牌は除く）
    riichi_opponents: list[int] = field(default_factory=list)  # 立直中の他家の席
    safe_tiles_34: set[int] = field(default_factory=set)       # 全リーチに対する現物の牌index


def iter_decisions(events: list[dict], actor: int) -> Iterator[DecisionContext]:
    """対象プレイヤーの各打牌局面の DecisionContext を順に返す。"""
    hands: list[list[str]] = [[], [], [], []]
    meld_descs: list[list[str]] = [[], [], [], []]
    meld_tiles: list[list[str]] = [[], [], [], []]
    rivers: list[list[str]] = [[], [], [], []]
    reached = [False, False, False, False]
    passed: dict[int, set[int]] = {}  # 立直席 -> 現物の牌index集合
    last_tsumo: list[str | None] = [None, None, None, None]
    junme = [0, 0, 0, 0]
    dora_markers: list[str] = []
    visible: list[str] = []
    ctx: dict = {}

    for ev in events:
        t = ev.get("type")
        if t == "start_kyoku":
            tehais = ev.get("tehais") or [[], [], [], []]
            for a in range(4):
                hands[a] = list(tehais[a])
                meld_descs[a] = []
                meld_tiles[a] = []
                rivers[a] = []
                reached[a] = False
                last_tsumo[a] = None
                junme[a] = 0
            passed = {}
            dora_markers = [ev["dora_marker"]] if ev.get("dora_marker") else []
            visible = list(dora_markers)
            oya = ev.get("oya", 0)
            ctx = {
                "bakaze": _BAKAZE.get(ev.get("bakaze", "E"), "東"),
                "kyoku": ev.get("kyoku", 1),
                "honba": ev.get("honba", 0),
                "oya": oya,
                "scores": ev.get("scores"),
            }
        elif t == "dora":
            if ev.get("dora_marker"):
                dora_markers.append(ev["dora_marker"])
                visible.append(ev["dora_marker"])
        elif t == "tsumo":
            a = ev["actor"]
            hands[a].append(ev["pai"])
            last_tsumo[a] = ev["pai"]
            junme[a] += 1
        elif t == "dahai":
            a = ev["actor"]
            if a == actor and not reached[a] and len(hands[a]) % 3 == 2:
                yield _build_context(ctx, a, hands[a], last_tsumo[a], ev["pai"],
                                     dora_markers, meld_descs[a], meld_tiles[a],
                                     visible, junme[a], reached, passed)
            # 状態更新
            hands[a] = without_tile(hands[a], ev["pai"])
            last_tsumo[a] = None
            rivers[a].append(ev["pai"])
            visible.append(ev["pai"])
            for r in passed:  # この打牌は各立直を通った（現物になる）
                passed[r].add(tile_to_index(ev["pai"]))
        elif t in ("pon", "chi", "daiminkan", "ankan"):
            a = ev["actor"]
            consumed = ev.get("consumed", [])
            for c in consumed:
                hands[a] = without_tile(hands[a], c)
                visible.append(c)
            meld_tiles[a].extend(consumed)
            if t != "ankan" and ev.get("pai"):
                meld_tiles[a].append(ev["pai"])
            meld_descs[a].append(_FURO_LABEL.get(t, "副露"))
            last_tsumo[a] = None
        elif t == "kakan":
            a = ev["actor"]
            pai = ev.get("pai", "")
            hands[a] = without_tile(hands[a], pai)
            if pai:
                visible.append(pai)
                meld_tiles[a].append(pai)
            last_tsumo[a] = None
        elif t == "reach_accepted":
            r = ev["actor"]
            reached[r] = True
            passed[r] = {tile_to_index(p) for p in rivers[r]}  # 自分の河は現物


def _build_context(ctx, a, hand, drawn, discard, dora_markers, meld_descs,
                   meld_tiles, visible, junme, reached, passed) -> DecisionContext:
    oya = ctx.get("oya", 0)
    riichi_opponents = [r for r in range(4) if reached[r] and r != a]
    if riichi_opponents:
        safe = set.intersection(*(passed[r] for r in riichi_opponents))
    else:
        safe = set()
    return DecisionContext(
        bakaze=ctx.get("bakaze", "東"),
        kyoku=ctx.get("kyoku", 1),
        honba=ctx.get("honba", 0),
        oya=oya,
        scores=ctx.get("scores"),
        actor=a,
        seat_wind=_JIKAZE[(a - oya) % 4],
        is_dealer=a == oya,
        junme=junme,
        hand=list(hand),
        drawn=drawn,
        discard=discard,
        dora_markers=list(dora_markers),
        meld_descs=list(meld_descs),
        meld_tiles=list(meld_tiles),
        visible_tiles=list(visible),
        riichi_opponents=riichi_opponents,
        safe_tiles_34=safe,
    )
