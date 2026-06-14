"""待ち推定（フリテン・スジ・壁/ノーチャンス）の厳密性テスト。"""

from jantama.review.danger import tile_danger
from jantama.review.mjai_state import iter_decisions
from jantama.review.waits import RYANMEN, wait_shapes, wait_tier, seen_counts
from jantama.tiles import tile_to_index

# seat1 が 9m,4m,E を切ってリーチ。actor0 は 3p を4枚抱える（=3pの壁）。
EVENTS = [
    {"type": "start_kyoku", "bakaze": "E", "kyoku": 1, "honba": 0, "oya": 0,
     "dora_marker": "1z", "scores": [25000, 25000, 25000, 25000],
     "tehais": [["3p", "3p", "3p", "3p", "6p", "6p", "7s", "7s", "8s", "8s", "E", "S", "W"],
                [], [], []]},
    {"type": "tsumo", "actor": 0, "pai": "9s"},
    {"type": "dahai", "actor": 0, "pai": "9s"},
    {"type": "tsumo", "actor": 1, "pai": "1z"},
    {"type": "dahai", "actor": 1, "pai": "9m"},
    {"type": "tsumo", "actor": 1, "pai": "2z"},
    {"type": "dahai", "actor": 1, "pai": "4m"},
    {"type": "tsumo", "actor": 1, "pai": "3z"},
    {"type": "reach", "actor": 1},
    {"type": "dahai", "actor": 1, "pai": "E", "tsumogiri": False},
    {"type": "reach_accepted", "actor": 1},
    {"type": "tsumo", "actor": 2, "pai": "9p"},
    {"type": "dahai", "actor": 2, "pai": "9p", "tsumogiri": True},
    {"type": "tsumo", "actor": 0, "pai": "5m"},
    {"type": "dahai", "actor": 0, "pai": "5m"},
]


def _ctx_seen():
    ctx = list(iter_decisions(EVENTS, actor=0))[-1]
    return ctx, seen_counts(ctx)


def _shapes(tile, ctx, seen):
    return wait_shapes(tile_to_index(tile), ctx.passed[1], seen)


def test_furiten_eliminates_wait():
    ctx, seen = _ctx_seen()
    assert _shapes("4m", ctx, seen) == set()  # リーチ者の河 → 待ちでない
    assert _shapes("9m", ctx, seen) == set()
    assert _shapes("E", ctx, seen) == set()   # 宣言牌もフリテン


def test_suji_eliminates_ryanmen():
    ctx, seen = _ctx_seen()
    # 4m切り → 1m,7m は両面が消える（片筋）。ただし他形は残る。
    assert RYANMEN not in _shapes("1m", ctx, seen)
    assert RYANMEN not in _shapes("7m", ctx, seen)
    assert _shapes("1m", ctx, seen)  # タンキ/シャンポンは残る（空ではない）


def test_penchan_is_not_counted_as_ryanmen():
    ctx, seen = _ctx_seen()
    # 7m の {8m,9m} はペンチャン。両面には数えない。
    shapes = _shapes("7m", ctx, seen)
    assert RYANMEN not in shapes
    assert "ペンチャン" in shapes


def test_wall_eliminates_ryanmen_needing_walled_tile():
    ctx, seen = _ctx_seen()
    # 3p が4枚見え → 3p を要する両面（1pの{2p,3p}、2pの{3p,4p}）は消える
    assert RYANMEN not in _shapes("1p", ctx, seen)
    assert RYANMEN not in _shapes("2p", ctx, seen)
    # 4p は {5p,6p} 側が生きているので両面は残る
    assert RYANMEN in _shapes("4p", ctx, seen)


def test_danger_tier_reflects_waits():
    ctx, seen = _ctx_seen()
    # 壁で両面の消えた1p は、両面の残る4p より安全
    assert tile_danger(tile_to_index("1p"), ctx, seen)[0] < tile_danger(tile_to_index("4p"), ctx, seen)[0]
    assert wait_tier(tile_to_index("4p"), ctx.passed[1], seen) == 3   # 両面あり=危険
