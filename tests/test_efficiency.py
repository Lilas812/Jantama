"""エンジン不要の牌効率レビューア（mjai ログ直読み）のテスト。"""

from pathlib import Path

from jantama.config import Config
from jantama.metrics import compute_metrics
from jantama.models import Explanation
from jantama.pipeline import analyze_report, default_reviewer
from jantama.review import EfficiencyReviewer, MortalReviewer
from jantama.sources import LocalLogSource

FIXTURE = Path(__file__).parent / "fixtures" / "sample_game.mjai.jsonl"

HAND0 = ["1m", "2m", "2m", "3m", "4m", "5p", "6p", "7p", "2s", "3s", "4s", "9s", "9s"]


def _events():
    return LocalLogSource(FIXTURE).load()


def test_efficiency_finds_shanten_loss():
    decisions = EfficiencyReviewer(actor=0).review(_events())
    assert decisions  # 何か検出される
    first = decisions[0]
    assert first.actual_action == "1m"
    assert first.recommended_action == "E"
    assert first.is_mistake is True
    assert first.junme == 1


def test_efficiency_metrics_consistent():
    first = EfficiencyReviewer(actor=0).review(_events())[0]
    m = compute_metrics(first)
    assert m.shanten_before == 0  # ツモE後はテンパイ可能
    assert m.shanten_after_actual == 1  # 1m切りで後退
    assert m.shanten_after_recommended == 0  # E切りでテンパイ維持


def test_default_reviewer_selects_engine():
    assert isinstance(default_reviewer(Config(engine="efficiency"), 0), EfficiencyReviewer)
    assert isinstance(default_reviewer(Config(engine="mortal"), 0), MortalReviewer)
    ako = default_reviewer(Config(engine="akochan"), 0)
    assert isinstance(ako, MortalReviewer) and ako.engine == "akochan"


def test_reach_discards_are_skipped():
    events = [
        {"type": "start_kyoku", "bakaze": "E", "kyoku": 1, "honba": 0, "oya": 0,
         "dora_marker": "9p", "tehais": [HAND0, [], [], []]},
        {"type": "tsumo", "actor": 0, "pai": "E"},
        {"type": "reach", "actor": 0},
        {"type": "dahai", "actor": 0, "pai": "1m", "tsumogiri": False},  # 宣言打牌=解析対象
        {"type": "reach_accepted", "actor": 0},
        {"type": "tsumo", "actor": 0, "pai": "7s"},
        {"type": "dahai", "actor": 0, "pai": "7s", "tsumogiri": True},  # 立直後=強制ツモ切り
    ]
    decisions = EfficiencyReviewer(actor=0).review(events)
    assert len(decisions) == 1  # 立直後の打牌は解析しない


class FakeExplainer:
    def explain(self, dp, metrics):
        return Explanation(decision=dp, metrics=metrics, text="(説明)")

    def summarize(self, stats, explanations):
        return "(総評)"


def test_analyze_report_efficiency_zero_setup():
    # Mortal も Claude も使わず、生の mjai ログから end-to-end でレポートが出る
    report = analyze_report(
        LocalLogSource(FIXTURE),
        config=Config(engine="efficiency"),
        explainer=FakeExplainer(),
    )
    assert report.stats.total_decisions == 2
    assert report.stats.mistakes == 2
    assert len(report.explanations) == 2
    assert report.summary == "(総評)"
    assert report.explanations[0].decision.note  # 牌効率ベースの注記が入る
