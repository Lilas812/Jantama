import json
from pathlib import Path
from types import SimpleNamespace

from jantama.config import Config
from jantama.explain import Explainer, build_user_prompt
from jantama.explain.prompts import SYSTEM_PROMPT
from jantama.metrics import compute_metrics
from jantama.review import parse_review_json

FIXTURE = Path(__file__).parent / "fixtures" / "sample_review.json"


def _decision():
    return parse_review_json(json.loads(FIXTURE.read_text(encoding="utf-8")))[0]


class FakeMessages:
    def __init__(self):
        self.captured = {}

    def create(self, **kwargs):
        self.captured = kwargs
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text="東を切ればテンパイです。")],
        )


class FakeClient:
    def __init__(self):
        self.messages = FakeMessages()


def test_build_user_prompt_contains_grounded_facts():
    dp = _decision()
    prompt = build_user_prompt(dp, compute_metrics(dp))
    assert "東1局" in prompt
    assert "推奨" in prompt
    assert "受け入れ" in prompt
    assert "ドラ" in prompt


def test_explainer_calls_claude_with_expected_params():
    dp = _decision()
    fake = FakeClient()
    explainer = Explainer(Config(), client=fake)
    exp = explainer.explain(dp, compute_metrics(dp))

    assert exp.text == "東を切ればテンパイです。"
    kwargs = fake.messages.captured
    assert kwargs["model"] == "claude-opus-4-8"
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert kwargs["output_config"] == {"effort": "medium"}
    assert kwargs["system"] == SYSTEM_PROMPT
    assert kwargs["messages"][0]["role"] == "user"


def test_severity_major_on_large_ev_gap():
    dp = _decision()  # ev_gap = 1.4 >> threshold*3
    exp = Explainer(Config(), client=FakeClient()).explain(dp, compute_metrics(dp))
    assert exp.severity == "major"


def test_refusal_handled_gracefully():
    class RefusingMessages(FakeMessages):
        def create(self, **kwargs):
            self.captured = kwargs
            return SimpleNamespace(stop_reason="refusal", content=[])

    client = SimpleNamespace(messages=RefusingMessages())
    dp = _decision()
    exp = Explainer(Config(), client=client).explain(dp, compute_metrics(dp))
    assert "安全フィルタ" in exp.text
