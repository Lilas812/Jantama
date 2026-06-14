"""踏み込んだ押し引き（危険度判定＋押す/降りる）のテスト。"""

from jantama.review import EfficiencyReviewer
from jantama.review.danger import _is_suji, tile_danger
from jantama.review.mjai_state import iter_decisions
from jantama.tiles import tile_to_index, to_34_array

# actor0 は3向聴（非テンパイ）。下家リーチ(9sが現物)。actor0 は安全牌を持つのに無筋5pを押す。
FOLD_EVENTS = [
    {"type": "start_kyoku", "bakaze": "E", "kyoku": 1, "honba": 0, "oya": 0,
     "dora_marker": "1z", "scores": [25000, 25000, 25000, 25000],
     "tehais": [["1m", "3m", "5m", "7m", "9m", "1p", "3p", "5p", "7p", "2s", "4s", "6s", "9s"],
                [], [], []]},
    {"type": "tsumo", "actor": 0, "pai": "9p"},
    {"type": "dahai", "actor": 0, "pai": "1p"},
    {"type": "tsumo", "actor": 1, "pai": "1m"},
    {"type": "reach", "actor": 1},
    {"type": "dahai", "actor": 1, "pai": "9s", "tsumogiri": False},
    {"type": "reach_accepted", "actor": 1},
    {"type": "tsumo", "actor": 2, "pai": "2z"},
    {"type": "dahai", "actor": 2, "pai": "2z", "tsumogiri": True},
    {"type": "tsumo", "actor": 3, "pai": "3z"},
    {"type": "dahai", "actor": 3, "pai": "3z", "tsumogiri": True},
    {"type": "tsumo", "actor": 0, "pai": "8m"},
    {"type": "dahai", "actor": 0, "pai": "5p"},  # 無筋5pを押す
]


def test_fold_recommended_when_behind_and_pushing_danger():
    d = EfficiencyReviewer(actor=0).review(FOLD_EVENTS)[-1]
    assert d.is_mistake is True
    assert d.recommended_action == "9s"   # 最も安全な現物へ降り
    assert "降り" in d.safety_note
    assert "無筋" in d.safety_note


def test_suji_logic():
    assert _is_suji(1, {4}) is True       # 1は4があれば片筋
    assert _is_suji(7, {4}) is True       # 7も4で片筋
    assert _is_suji(4, {1}) is False      # 4(中筋)は片側だけでは不可
    assert _is_suji(4, {1, 7}) is True    # 両側そろえば中筋
    assert _is_suji(5, {2}) is False
    assert _is_suji(5, {2, 8}) is True


def test_tile_danger_tiers():
    ctx = list(iter_decisions(FOLD_EVENTS, actor=0))[-1]
    seen = to_34_array(ctx.visible_tiles)
    assert tile_danger(tile_to_index("9s"), ctx, seen)[0] == 0   # 現物
    assert tile_danger(tile_to_index("5p"), ctx, seen)[0] == 3   # 無筋中張＝危険


def test_no_riichi_means_no_pushfold():
    # リーチ前の局面（1巡目）は押し引きノートが出ない（純粋な牌効率判断）
    d = EfficiencyReviewer(actor=0).review(FOLD_EVENTS[:3])[0]
    assert d.safety_note == ""
