"""副露(鳴き)を含む手の牌効率計算のテスト。"""

from jantama.explain import build_user_prompt
from jantama.metrics import calc_shanten, compute_metrics
from jantama.models import DecisionPoint
from jantama.tiles import to_34_array


def _meld_decision() -> DecisionPoint:
    # 鳴き1（概要牌11枚）。234m 567p 99s 23s + ツモ8s。
    # 推奨=8s切りで 1s/4s 待ちのテンパイ、実際=9s切りで1向聴に後退。
    return DecisionPoint(
        round_wind="東", kyoku=1, honba=0, seat=0, seat_wind="東", is_dealer=True,
        junme=8,
        hand=["2m", "3m", "4m", "5p", "6p", "7p", "9s", "9s", "2s", "3s", "8s"],
        drawn_tile="8s", dora_markers=[], melds=["ポン 東"],
        actual_action="9s", recommended_action="8s",
    )


def test_meld_hand_is_now_computed():
    m = compute_metrics(_meld_decision())
    assert m.available is True
    assert m.num_melds == 1  # 概要牌11枚から鳴き1と判定


def test_meld_hand_shanten():
    m = compute_metrics(_meld_decision())
    assert m.shanten_before == 0  # 8s を切ればテンパイ
    assert m.shanten_after_recommended == 0
    assert m.shanten_after_actual == 1  # 9s 切りは1向聴に後退


def test_meld_hand_ukeire():
    m = compute_metrics(_meld_decision())
    assert set(m.ukeire_tiles_recommended) == {"1s", "4s"}
    assert m.ukeire_after_recommended == 8  # 1s4s 各4枚


def test_open_flag_excludes_chiitoitsu():
    # 6対子の手は七対子ありなら聴牌(0)だが、鳴いた手では七対子は不可なので
    # allow_special=False では面子手として正しく評価される。
    chiitoi = to_34_array(
        ["1m", "1m", "3m", "3m", "5m", "5m", "7m", "7m", "9m", "9m", "2p", "2p", "4p"]
    )
    assert calc_shanten(chiitoi, allow_special=True) == 0
    assert calc_shanten(chiitoi, allow_special=False) == 3


def test_num_melds_from_tile_count():
    # 鳴き2（概要牌8枚）。234m 567p + 99s（待ち無しの完成形）。
    dp = DecisionPoint(
        round_wind="東", kyoku=1, honba=0, seat=0, seat_wind="東", is_dealer=False,
        junme=10, hand=["2m", "3m", "4m", "5p", "6p", "7p", "9s", "9s"],
        drawn_tile="9s", dora_markers=[], melds=["チー", "ポン"],
        actual_action="9s", recommended_action="9s",
    )
    m = compute_metrics(dp)
    assert m.num_melds == 2
    assert m.shanten_before == -1  # 2面子+雀頭+鳴き2 = 和了形


def _open_dora_dp() -> DecisionPoint:
    # ドラ表示 1m → ドラ 2m。手牌に 2m は無いが、ポンした 2m が副露に3枚。
    return DecisionPoint(
        round_wind="東", kyoku=1, honba=0, seat=0, seat_wind="東", is_dealer=False,
        junme=9,
        hand=["3m", "4m", "5m", "6m", "7m", "8m", "2s", "3s", "4s", "9p", "9p"],
        drawn_tile="8m", dora_markers=["1m"], melds=["ポン 2m"],
        meld_tiles=["2m", "2m", "2m"],
        actual_action="9p", recommended_action="9p",
    )


def test_meld_dora_counted_when_meld_tiles_known():
    m = compute_metrics(_open_dora_dp())
    assert m.dora_in_hand == 3  # 副露の 2m×3 をドラとして集計


def test_prompt_labels_dora_including_melds():
    dp = _open_dora_dp()
    prompt = build_user_prompt(dp, compute_metrics(dp))
    assert "ドラ（手牌＋副露）" in prompt
