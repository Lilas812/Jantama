import json
from pathlib import Path

from jantama.config import Config
from jantama.metrics import compute_metrics
from jantama.models import Explanation
from jantama.pipeline import analyze, select_decisions
from jantama.review import parse_review_json

FIXTURE = Path(__file__).parent / "fixtures" / "sample_review.json"


def _decisions():
    return parse_review_json(json.loads(FIXTURE.read_text(encoding="utf-8")))


class StubSource:
    def load(self):
        return []


class FakeReviewer:
    def __init__(self, decisions):
        self._decisions = decisions

    def review(self, mjai_events):
        return self._decisions


class FakeExplainer:
    def explain(self, dp, metrics):
        return Explanation(decision=dp, metrics=metrics, text="(説明)")


def test_select_decisions_keeps_mistakes_only():
    decisions = _decisions()
    chosen = select_decisions(decisions, Config())
    assert len(chosen) == 1  # 唯一のミスが選ばれる


def test_select_decisions_ignores_non_mistakes():
    dp = _decisions()[0]
    dp.recommended_action = dp.actual_action  # ミスでなくする
    assert select_decisions([dp], Config()) == []


def test_analyze_end_to_end_with_fakes():
    explanations = analyze(
        StubSource(),
        config=Config(),
        reviewer=FakeReviewer(_decisions()),
        explainer=FakeExplainer(),
    )
    assert len(explanations) == 1
    assert explanations[0].text == "(説明)"
    assert explanations[0].decision.recommended_action == "E"
