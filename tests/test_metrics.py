import json
from pathlib import Path

from jantama.metrics import compute_metrics
from jantama.review import parse_review_json

FIXTURE = Path(__file__).parent / "fixtures" / "sample_review.json"


def _decision():
    return parse_review_json(json.loads(FIXTURE.read_text(encoding="utf-8")))[0]


def test_metrics_detect_shanten_loss():
    dp = _decision()
    m = compute_metrics(dp)
    assert m.available is True
    # 打牌前はテンパイ可能な形（14枚）
    assert m.shanten_before == 0
    # 推奨(東切り)はテンパイ維持、実際(1m切り)は1向聴に後退
    assert m.shanten_after_recommended == 0
    assert m.shanten_after_actual == 1


def test_metrics_recommended_ukeire_includes_winning_tile():
    m = compute_metrics(_decision())
    assert m.ukeire_after_recommended is not None
    assert m.ukeire_after_recommended > 0
    assert "3m" in m.ukeire_tiles_recommended  # 1m2m の両面、3mで和了


def test_metrics_counts_dora_in_hand():
    # ドラ表示 1m → ドラは 2m。手牌に 2m が 2 枚。
    m = compute_metrics(_decision())
    assert m.dora_in_hand == 2
