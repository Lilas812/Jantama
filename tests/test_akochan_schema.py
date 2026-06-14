"""実際の akochan エンジン出力スキーマに対するパース＋補完の検証。

実機 mjai-reviewer -e akochan の出力を確認して作成したフィクスチャ。
Mortal と異なり expected/actual は Event 配列、details は pt ベースの review、
acceptance(一致/許容/非一致) を持つ。engine は "Akochan"（大文字）。
"""

import json
from pathlib import Path

from jantama.metrics import compute_metrics
from jantama.review import parse_and_enrich

FIXTURE = Path(__file__).parent / "fixtures" / "sample_akochan_real.json"


def _data():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_detects_and_parses_akochan_schema():
    decisions = parse_and_enrich(_data())
    assert len(decisions) == 2
    d = decisions[0]
    assert d.round_wind == "東" and d.kyoku == 1 and d.junme == 1
    assert d.actual_action == "3m"        # actual 配列の dahai 牌
    assert d.recommended_action == "2p"   # 非一致なので expected を採用
    assert d.is_mistake is True
    assert d.actual_ev == 6.168 and d.recommended_ev == 6.443  # pt_exp_total
    assert "非一致" in d.note


def test_tolerable_move_is_not_flagged():
    # acceptance が「許容」の手は、推奨と違っても要改善にしない
    d = parse_and_enrich(_data())[1]
    assert d.actual_action == "9s"
    assert d.recommended_action == "9s"   # tolerable → 実打を採用（ミス扱いしない）
    assert d.is_mistake is False


def test_hand_enriched_and_metrics_computable():
    d = parse_and_enrich(_data())[0]
    assert d.hand and len(d.hand) == 14    # mjai_log から手牌補完
    assert d.dora_markers == ["4m"]
    m = compute_metrics(d)
    assert m.available
    assert m.shanten_before is not None
