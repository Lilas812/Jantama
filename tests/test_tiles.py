from jantama import tiles


def test_normalize_red_and_z():
    assert tiles.normalize("0m") == "5mr"
    assert tiles.normalize("0p") == "5pr"
    assert tiles.normalize("1z") == "E"
    assert tiles.normalize("7z") == "C"
    assert tiles.normalize("5m") == "5m"


def test_tile_to_index_roundtrip():
    for idx in range(34):
        pai = tiles.index_to_tile(idx)
        assert tiles.tile_to_index(pai) == idx


def test_red_five_maps_to_normal_index():
    assert tiles.tile_to_index("5mr") == tiles.tile_to_index("5m")
    assert tiles.tile_to_index("0p") == tiles.tile_to_index("5p")
    assert tiles.is_red_five("5sr")
    assert not tiles.is_red_five("5s")


def test_to_34_array_counts():
    arr = tiles.to_34_array(["1m", "1m", "9p", "E", "E", "E"])
    assert arr[tiles.tile_to_index("1m")] == 2
    assert arr[tiles.tile_to_index("9p")] == 1
    assert arr[tiles.tile_to_index("E")] == 3
    assert sum(arr) == 6


def test_next_dora():
    assert tiles.next_dora("1m") == "2m"
    assert tiles.next_dora("9m") == "1m"  # 巡回
    assert tiles.next_dora("9s") == "1s"
    assert tiles.next_dora("N") == "E"  # 北→東
    assert tiles.next_dora("C") == "P"  # 中→白


def test_hand_to_jp():
    s = tiles.hand_to_jp(["3m", "1m", "2m", "5pr", "E", "E"])
    assert "123萬" in s
    assert "0筒" in s  # 赤5筒は 0 表記で並ぶ
    assert "東東" in s
