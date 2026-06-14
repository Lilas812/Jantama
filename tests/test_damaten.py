"""黙テン（立直なしテンパイ）推定と脅威統合のテスト。"""

from jantama.review.mjai_state import DecisionContext
from jantama.review.tenpai_read import (
    consecutive_tsumogiri,
    list_threats,
    tenpai_probability,
)
from jantama.tiles import tile_to_index


def _ctx(**kw) -> DecisionContext:
    base = dict(
        bakaze="東", kyoku=1, honba=0, oya=0, scores=None, actor=0, seat_wind="東",
        is_dealer=True, junme=10, hand=["1m"], drawn=None, discard="1m",
        dora_markers=[], meld_descs=[], meld_tiles=[], visible_tiles=[],
        riichi_opponents=[], safe_tiles_34=set(), passed={},
        rivers=[[], [], [], []], meld_counts=[0, 0, 0, 0], reached_seats=[],
    )
    base.update(kw)
    return DecisionContext(**base)


def test_consecutive_tsumogiri_counts_trailing():
    ctx = _ctx(rivers=[[], [("1m", False), ("2m", True), ("3m", True)], [], []])
    assert consecutive_tsumogiri(ctx, 1) == 2  # 末尾の手出しでない2枚


def test_tenpai_probability_rises_with_melds_and_tsumogiri():
    low, _ = tenpai_probability(_ctx(junme=3), 1)
    high, reasons = tenpai_probability(
        _ctx(junme=12, meld_counts=[0, 3, 0, 0],
             rivers=[[], [("1m", True), ("2m", True), ("3m", True)], [], []]), 1)
    assert high > low
    assert high >= 0.6                # 終盤＋3副露＋連続ツモ切り → 濃厚
    assert any("副露" in r for r in reasons)


def test_damaten_becomes_threat_with_genbutsu():
    ctx = _ctx(junme=13, meld_counts=[0, 0, 3, 0],
               rivers=[[], [], [("9p", True), ("E", True), ("S", True)], []])
    threats = list_threats(ctx)
    th = next(t for t in threats if t.seat == 2)
    assert th.kind == "damaten"
    assert tile_to_index("9p") in th.genbutsu   # その家の河は現物


def test_riichi_seat_not_double_counted_as_damaten():
    ctx = _ctx(junme=13, meld_counts=[0, 0, 3, 0], riichi_opponents=[2],
               reached_seats=[2], passed={2: {tile_to_index("9p")}},
               rivers=[[], [], [("9p", True)], []])
    kinds = {t.seat: t.kind for t in list_threats(ctx)}
    assert kinds[2] == "riichi"  # 立直済みは黙テンに二重計上しない


def test_no_threat_when_quiet_early():
    # 序盤・副露なし・ツモ切り少 → 脅威なし
    assert list_threats(_ctx(junme=3)) == []
