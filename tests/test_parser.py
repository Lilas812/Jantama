import json
from pathlib import Path

from jantama.review import parse_review_json

FIXTURE = Path(__file__).parent / "fixtures" / "sample_review.json"


def _load():
    return parse_review_json(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_parses_single_decision():
    decisions = _load()
    assert len(decisions) == 1


def test_decision_fields():
    dp = _load()[0]
    assert dp.round_wind == "東"
    assert dp.kyoku == 1
    assert dp.seat == 0
    assert dp.seat_wind == "東"  # 東1局・player0 は親(東家)
    assert dp.is_dealer is True
    assert dp.junme == 6
    assert dp.drawn_tile == "E"
    assert dp.dora_markers == ["1m"]


def test_decision_actions_and_ev():
    dp = _load()[0]
    assert dp.actual_action == "1m"
    assert dp.recommended_action == "E"
    assert dp.actual_ev == 12.1
    assert dp.recommended_ev == 13.5
    assert dp.is_mistake is True
    assert dp.ev_gap == 13.5 - 12.1
