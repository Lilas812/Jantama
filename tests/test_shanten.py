from jantama.metrics import calc_shanten, calc_ukeire
from jantama.tiles import index_to_tile, tile_to_index, to_34_array


def test_complete_hand_is_minus_one():
    hand = to_34_array(["1m", "2m", "3m", "4p", "5p", "6p", "7s", "8s", "9s", "E", "E", "S", "S", "S"])
    assert calc_shanten(hand) == -1


def test_tenpai_is_zero():
    # 123m 456p 789s 11p + 待ち (East single -> need pair) ... use a clear tenpai
    hand = to_34_array(["1m", "2m", "3m", "4p", "5p", "6p", "7s", "8s", "9s", "E", "E", "S", "S"])
    assert calc_shanten(hand) == 0


def test_ukeire_tenpai_counts_winning_tile():
    # 123m 456p 789s 99s + 2m3m : 13枚, 1m/4m待ちのテンパイ
    hand13 = to_34_array(
        ["1m", "2m", "3m", "4p", "5p", "6p", "7s", "8s", "9s", "9s", "9s", "2m", "3m"]
    )
    total, accepted = calc_ukeire(hand13)
    assert total > 0
    accepted_tiles = {index_to_tile(i) for i in accepted}
    # 2m3m の両面なので 1m と 4m を受け入れる
    assert "1m" in accepted_tiles
    assert "4m" in accepted_tiles


def test_ukeire_respects_visible_tiles():
    hand13 = to_34_array(
        ["1m", "2m", "3m", "4p", "5p", "6p", "7s", "8s", "9s", "9s", "9s", "2m", "3m"]
    )
    visible = [0] * 34
    visible[tile_to_index("1m")] = 2  # 1m が場に 2 枚見えている
    base_total, _ = calc_ukeire(hand13)
    reduced_total, _ = calc_ukeire(hand13, visible)
    assert reduced_total == base_total - 2
