"""複数局・副露・ドラ追加・立直を含む実戦寄り mjai ログでの通し検証。"""

from pathlib import Path

from jantama.config import Config
from jantama.metrics import compute_metrics
from jantama.models import Explanation
from jantama.pipeline import analyze_report
from jantama.review import EfficiencyReviewer
from jantama.sources import LocalLogSource

FIXTURE = Path(__file__).parent / "fixtures" / "sample_game_full.mjai.jsonl"


def _decisions():
    return EfficiencyReviewer(actor=0).review(LocalLogSource(FIXTURE).load())


def test_processes_multiple_kyoku():
    decisions = _decisions()
    assert {(d.round_wind, d.kyoku) for d in decisions} == {("東", 1), ("東", 2)}
    assert len(decisions) == 4


def test_handles_melds_and_riichi_robustly():
    decisions = _decisions()
    metrics = [compute_metrics(d) for d in decisions]
    assert all(m.available for m in metrics)  # どの局面も計算できている
    assert sum(1 for m in metrics if m.num_melds > 0) == 2  # ポン後の2局面は鳴き手
    assert sum(1 for d in decisions if d.safety_note) == 1  # 東2のリーチ局面


class FakeExplainer:
    def explain(self, dp, metrics):
        return Explanation(decision=dp, metrics=metrics, text="(説明)")

    def summarize(self, stats, explanations):
        return "(総評)"


def test_full_pipeline_clean_game_gives_summary_without_findings():
    # この牌譜では actor0 に明確なミスが無い。総評は出るが個別指摘は0件。
    report = analyze_report(
        LocalLogSource(FIXTURE),
        config=Config(engine="efficiency"),
        explainer=FakeExplainer(),
    )
    assert report.stats.total_decisions == 4
    assert report.stats.mistakes == 0
    assert report.explanations == []
    assert report.summary == "(総評)"
