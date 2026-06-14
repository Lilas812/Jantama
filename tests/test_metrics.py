import json
from pathlib import Path

from jantama.metrics import compute_metrics
from jantama.models import DecisionPoint
from jantama.review import parse_review_json

FIXTURE = Path(__file__).parent / "fixtures" / "sample_review.json"


def _decision():
    return parse_review_json(json.loads(FIXTURE.read_text(encoding="utf-8")))[0]


def _tenpai_dp(visible: list[str]) -> DecisionPoint:
    # 東を切れば 3m 待ちのテンパイ。手牌に 3m が1枚あるので通常は残り3枚。
    return DecisionPoint(
        round_wind="東", kyoku=1, honba=0, seat=0, seat_wind="東", is_dealer=True,
        junme=5,
        hand=["1m", "2m", "2m", "3m", "4m", "5p", "6p", "7p", "2s", "3s", "4s", "9s", "9s", "E"],
        drawn_tile="E", dora_markers=[], visible_tiles=visible,
        actual_action="1m", recommended_action="E",
    )


def test_visible_tiles_reduce_ukeire():
    # 場に見えている牌が無ければ 3m の残りは 3 枚
    assert compute_metrics(_tenpai_dp([])).ukeire_after_recommended == 3
    # 河などに 3m が 2 枚見えていれば残りは 1 枚
    assert compute_metrics(_tenpai_dp(["3m", "3m"])).ukeire_after_recommended == 1


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
