"""押し引き（立直・現物）の追跡とベタ降り判定のテスト。"""

from jantama.config import Config
from jantama.explain import build_user_prompt
from jantama.metrics import compute_metrics
from jantama.review import EfficiencyReviewer
from jantama.review.mjai_state import iter_decisions
from jantama.tiles import tile_to_index

# 下家(seat1)が 9p を切って立直。actor0 は危険牌 1m を引くが、現物の 9p で
# ベタ降りする局面。
EVENTS = [
    {"type": "start_kyoku", "bakaze": "E", "kyoku": 1, "honba": 0, "oya": 0,
     "dora_marker": "E", "scores": [25000, 25000, 25000, 25000],
     "tehais": [
         ["2m", "3m", "4m", "5m", "6m", "7m", "2p", "3p", "4p", "5s", "6s", "9p", "9p"],
         ["9p", "1s", "2s", "3s", "4s", "5s", "6s", "7s", "8s", "9s", "E", "S", "W"],
         ["1m", "1m", "2m", "2m", "3m", "3m", "4m", "4m", "5m", "5m", "6m", "6m", "7m"],
         ["1p", "1p", "2p", "2p", "3p", "3p", "4p", "4p", "5p", "5p", "6p", "6p", "7p"],
     ]},
    {"type": "tsumo", "actor": 0, "pai": "W"},
    {"type": "dahai", "actor": 0, "pai": "W", "tsumogiri": True},  # 立直前・テンパイ維持
    {"type": "tsumo", "actor": 1, "pai": "1m"},
    {"type": "reach", "actor": 1},
    {"type": "dahai", "actor": 1, "pai": "9p", "tsumogiri": False},  # 立直宣言で9p
    {"type": "reach_accepted", "actor": 1},
    {"type": "tsumo", "actor": 2, "pai": "8m"},
    {"type": "dahai", "actor": 2, "pai": "8m", "tsumogiri": True},
    {"type": "tsumo", "actor": 3, "pai": "8p"},
    {"type": "dahai", "actor": 3, "pai": "8p", "tsumogiri": True},
    {"type": "tsumo", "actor": 0, "pai": "1m"},
    {"type": "dahai", "actor": 0, "pai": "9p", "tsumogiri": False},  # 現物でベタ降り
    {"type": "end_kyoku"},
]


def test_tracker_tracks_riichi_and_genbutsu():
    contexts = list(iter_decisions(EVENTS, actor=0))
    assert len(contexts) == 2
    turn2 = contexts[1]
    assert turn2.junme == 2
    assert turn2.riichi_opponents == [1]  # 下家がリーチ
    assert tile_to_index("9p") in turn2.safe_tiles_34  # 9p は現物
    assert tile_to_index("1m") not in turn2.safe_tiles_34  # 1m は無筋


def test_safe_fold_not_flagged_as_mistake():
    decisions = EfficiencyReviewer(actor=0).review(EVENTS)
    fold = decisions[1]  # 立直後の局面
    assert fold.actual_action == "9p"
    # 効率最善は 1m(テンパイ維持)だが、現物でのベタ降りはミス扱いしない
    assert fold.recommended_action == "9p"
    assert fold.is_mistake is False
    assert "リーチ" in fold.safety_note
    assert "現物" in fold.safety_note


def test_no_riichi_no_safety_note():
    decisions = EfficiencyReviewer(actor=0).review(EVENTS)
    assert decisions[0].safety_note == ""  # 1巡目は立直前


def test_safety_note_appears_in_prompt():
    fold = EfficiencyReviewer(actor=0).review(EVENTS)[1]
    prompt = build_user_prompt(fold, compute_metrics(fold))
    assert "押し引き" in prompt
    assert "リーチ" in prompt
