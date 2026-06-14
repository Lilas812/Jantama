"""外部アダプタ(mjai-reviewer / 雀魂変換)の堅牢化と補完照合のテスト。"""

from pathlib import Path

import pytest

from jantama.config import Config
from jantama.models import DecisionPoint
from jantama.review import MortalReviewer
from jantama.review.mjai_state import enrich_decisions
from jantama.sources import LocalLogSource, MahjongSoulSource

FULL = Path(__file__).parent / "fixtures" / "sample_game_full.mjai.jsonl"


def _bare(**kw) -> DecisionPoint:
    base = dict(
        round_wind="東", kyoku=1, honba=0, seat=0, seat_wind="東", is_dealer=True,
        junme=1, hand=[], drawn_tile=None, dora_markers=[],
        actual_action="W", recommended_action="W",
    )
    base.update(kw)
    return DecisionPoint(**base)


def test_enrich_matches_same_turn_decisions_in_order():
    # 東1局は同じ1巡目に「Wを切る」「ポン後にEを切る」の2局面がある。
    events = LocalLogSource(FULL).load()
    dp_a = _bare(junme=1, actual_action="W")  # 1番目=閉じた局面
    dp_b = _bare(junme=1, actual_action="E")  # 2番目=ポン後(鳴き手)
    enrich_decisions([dp_a, dp_b], events, actor=0)
    assert dp_a.visible_tiles and dp_b.visible_tiles
    assert dp_a.meld_tiles == []        # 1番目は副露なし
    assert dp_b.meld_tiles != []        # 2番目はポンの 5p が入る


def test_mjai_reviewer_command_template():
    cfg = Config(mjai_reviewer_cmd="rev -i {in} -o {out} -a {actor} --cfg {model}",
                 mortal_model_path="/m/cfg.toml")
    cmd = MortalReviewer(cfg, actor=2).build_command("IN.json", "OUT.json")
    assert cmd == ["rev", "-i", "IN.json", "-o", "OUT.json", "-a", "2", "--cfg", "/m/cfg.toml"]


def test_mortal_reviewer_validates_actor():
    with pytest.raises(ValueError):
        MortalReviewer(actor=5)


def test_majsoul_fetch_command_template():
    cfg = Config(majsoul_fetch_cmd="conv {id} -o {out} -t {token}",
                 majsoul_access_token="TK")
    src = MahjongSoulSource("https://game.mahjongsoul.com/?paipu=ID123-aa_a99", cfg)
    assert src.paipu_id == "ID123-aa"
    assert src.build_command("OUT.json") == ["conv", "ID123-aa", "-o", "OUT.json", "-t", "TK"]
