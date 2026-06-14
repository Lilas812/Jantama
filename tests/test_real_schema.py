"""実際の mjai-reviewer --json 出力スキーマに対するパース＋補完の検証。

実出力は手牌を state に持ち、トップレベルに mjai_log（全イベント）を含む。
parse_and_enrich がレビュー結果を読み、mjai_log から手牌・ドラ・盤面を補完する。
"""

import json
from pathlib import Path

from jantama.metrics import compute_metrics
from jantama.review import parse_and_enrich

FIXTURE = Path(__file__).parent / "fixtures" / "sample_review_real.json"


def _data():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_parses_real_schema_entry():
    decisions = parse_and_enrich(_data())
    assert len(decisions) == 1
    dp = decisions[0]
    assert dp.round_wind == "東"
    assert dp.kyoku == 1
    assert dp.seat_wind == "東" and dp.is_dealer is True
    assert dp.actual_action == "1m"        # actual は Event dict から抽出
    assert dp.recommended_action == "E"    # expected から
    assert dp.actual_ev == 12.1
    assert dp.recommended_ev == 13.5


def test_board_state_filled_from_mjai_log():
    dp = parse_and_enrich(_data())[0]
    assert dp.hand           # state に無くても mjai_log から補完される
    assert dp.drawn_tile == "E"
    assert dp.dora_markers == ["9p"]
    assert dp.visible_tiles  # ドラ表示などが入る


def test_metrics_work_on_real_schema():
    dp = parse_and_enrich(_data())[0]
    m = compute_metrics(dp)
    assert m.shanten_before == 0          # ツモE後はテンパイ可能
    assert m.shanten_after_actual == 1    # 1m切りで後退
    assert m.shanten_after_recommended == 0  # E切りでテンパイ維持
