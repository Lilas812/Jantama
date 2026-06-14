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


def test_enrich_matches_by_kyoku_and_junme():
    # 東1局: 1巡目に W を切り、ポン後の2巡目に E を切る（mjai-reviewer 同様
    # チー/ポンで巡目+1）。(局,本場,巡目)で正しく対応づく。
    events = LocalLogSource(FULL).load()
    dp1 = _bare(junme=1, actual_action="W")  # 閉じた局面
    dp2 = _bare(junme=2, actual_action="E")  # ポン後(鳴き手)
    enrich_decisions([dp1, dp2], events, actor=0)
    assert dp1.hand and dp2.hand            # 手牌が mjai_log から補完される
    assert dp1.meld_tiles == []             # 1巡目は副露なし
    assert dp2.meld_tiles != []             # ポンの 5p が入る


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
