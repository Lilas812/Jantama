import json
from pathlib import Path
from types import SimpleNamespace

from jantama.config import Config
from jantama.explain import Explainer, build_summary_prompt
from jantama.explain.prompts import SUMMARY_SYSTEM_PROMPT
from jantama.metrics import compute_metrics
from jantama.models import DecisionPoint, Explanation, GameReport
from jantama.pipeline import analyze_report, compute_stats
from jantama.review import parse_review_json

FIXTURE = Path(__file__).parent / "fixtures" / "sample_review.json"


def _decisions():
    return parse_review_json(json.loads(FIXTURE.read_text(encoding="utf-8")))


def _mk(actual: str, recommended: str, ev_gap: float | None = None) -> DecisionPoint:
    ev_a = ev_r = None
    if ev_gap is not None:
        ev_a, ev_r = 10.0, 10.0 + ev_gap
    return DecisionPoint(
        round_wind="東", kyoku=1, honba=0, seat=0, seat_wind="東", is_dealer=True,
        junme=3, hand=[], drawn_tile=None, dora_markers=[],
        actual_action=actual, recommended_action=recommended,
        actual_ev=ev_a, recommended_ev=ev_r,
    )


def test_compute_stats():
    decisions = [_mk("1m", "E", 1.4), _mk("5p", "5p", 0.0), _mk("9s", "9s", 0.0)]
    s = compute_stats(decisions)
    assert s.total_decisions == 3
    assert s.mistakes == 1
    assert s.matches == 2
    assert abs(s.match_rate - 2 / 3) < 1e-9
    assert abs(s.total_ev_loss - 1.4) < 1e-9


def test_match_rate_none_when_empty():
    assert compute_stats([]).match_rate is None


def _one_explanation() -> Explanation:
    dp = _decisions()[0]
    return Explanation(decision=dp, metrics=compute_metrics(dp), text="x", severity="major")


def test_build_summary_prompt_contains_grounded_stats():
    stats = compute_stats(_decisions())
    prompt = build_summary_prompt(stats, [_one_explanation()])
    assert "推奨一致率" in prompt
    assert "個別の指摘" in prompt
    assert "東1局" in prompt
    assert "改善点" in prompt


class FakeMessages:
    def __init__(self):
        self.captured = {}

    def create(self, **kwargs):
        self.captured = kwargs
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text="全体に手なりが多めです。")],
        )


def test_summarize_uses_summary_system_prompt():
    fake = SimpleNamespace(messages=FakeMessages())
    text = Explainer(Config(), client=fake).summarize(
        compute_stats(_decisions()), [_one_explanation()]
    )
    assert text == "全体に手なりが多めです。"
    assert fake.messages.captured["system"] == SUMMARY_SYSTEM_PROMPT
    assert fake.messages.captured["model"] == "claude-opus-4-8"


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

    def summarize(self, stats, explanations):
        return "(総評)"


def test_analyze_report_assembles_everything():
    report = analyze_report(
        StubSource(),
        config=Config(),
        reviewer=FakeReviewer(_decisions()),
        explainer=FakeExplainer(),
    )
    assert isinstance(report, GameReport)
    assert report.stats.total_decisions == 1
    assert report.stats.mistakes == 1
    assert len(report.explanations) == 1
    assert report.summary == "(総評)"


def test_analyze_report_can_skip_summary():
    report = analyze_report(
        StubSource(),
        config=Config(),
        reviewer=FakeReviewer(_decisions()),
        explainer=FakeExplainer(),
        summarize=False,
    )
    assert report.summary == ""
