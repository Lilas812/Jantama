"""牌の表記ユーティリティ。

内部表現は mjai 形式の文字列に統一する:
    数牌  : "1m".."9m" (萬子) / "1p".."9p" (筒子) / "1s".."9s" (索子)
    赤5   : "5mr" / "5pr" / "5sr"  (天鳳形式の "0m"/"0p"/"0s" も受理)
    字牌  : "E"(東) "S"(南) "W"(西) "N"(北) "P"(白) "F"(發) "C"(中)

`mahjong` ライブラリの向聴計算は 34 種のカウント配列を使うため、
mjai 文字列 ↔ 34 配列インデックス の変換を提供する。
"""

from __future__ import annotations

# 34 配列のインデックス: 萬0-8 / 筒9-17 / 索18-26 / 字27-33
HONOR_TO_INDEX = {"E": 27, "S": 28, "W": 29, "N": 30, "P": 31, "F": 32, "C": 33}
INDEX_TO_HONOR = {v: k for k, v in HONOR_TO_INDEX.items()}

# 日本語表示用
HONOR_JP = {
    "E": "東", "S": "南", "W": "西", "N": "北",
    "P": "白", "F": "發", "C": "中",
}
SUIT_JP = {"m": "萬", "p": "筒", "s": "索"}


_Z_TO_LETTER = {"1z": "E", "2z": "S", "3z": "W", "4z": "N", "5z": "P", "6z": "F", "7z": "C"}


def normalize(pai: str) -> str:
    """赤5・天鳳/z 形式を mjai の正規形に寄せる。"""
    pai = pai.strip()
    # 天鳳の赤5: 0m/0p/0s → 5mr/5pr/5sr
    if len(pai) == 2 and pai[0] == "0" and pai[1] in "mps":
        return f"5{pai[1]}r"
    # 字牌の z 表記: 1z..7z → E..C
    if pai in _Z_TO_LETTER:
        return _Z_TO_LETTER[pai]
    return pai


def tile_to_index(pai: str) -> int:
    """mjai 牌 → 34 配列インデックス。赤5は通常の5として扱う。"""
    pai = normalize(pai)
    if pai in HONOR_TO_INDEX:
        return HONOR_TO_INDEX[pai]
    # 数牌（赤5の末尾 r は無視）
    num = int(pai[0])
    suit = pai[1]
    if suit == "m":
        return num - 1
    if suit == "p":
        return 9 + num - 1
    if suit == "s":
        return 18 + num - 1
    raise ValueError(f"未知の牌: {pai!r}")


def index_to_tile(index: int) -> str:
    """34 配列インデックス → mjai 牌（赤は区別しない）。"""
    if index in INDEX_TO_HONOR:
        return INDEX_TO_HONOR[index]
    if 0 <= index <= 8:
        return f"{index + 1}m"
    if 9 <= index <= 17:
        return f"{index - 9 + 1}p"
    if 18 <= index <= 26:
        return f"{index - 18 + 1}s"
    raise ValueError(f"範囲外のインデックス: {index}")


def is_red_five(pai: str) -> bool:
    pai = normalize(pai)
    return len(pai) == 3 and pai.endswith("r")


def to_34_array(pais: list[str]) -> list[int]:
    """mjai 牌のリスト → 34 種のカウント配列。"""
    arr = [0] * 34
    for pai in pais:
        arr[tile_to_index(pai)] += 1
    return arr


def next_dora_index(marker: str) -> int:
    """ドラ表示牌 → ドラ本体の 34 インデックス。

    数牌は同スートで 9→1 に巡回。字牌は 風(東→南→西→北→東)・三元(白→發→中→白)で巡回。
    """
    idx = tile_to_index(marker)
    if idx <= 8:  # 萬
        return (idx + 1) % 9
    if 9 <= idx <= 17:  # 筒
        return 9 + ((idx - 9 + 1) % 9)
    if 18 <= idx <= 26:  # 索
        return 18 + ((idx - 18 + 1) % 9)
    if 27 <= idx <= 30:  # 風 E,S,W,N
        return 27 + ((idx - 27 + 1) % 4)
    return 31 + ((idx - 31 + 1) % 3)  # 三元 P,F,C


def next_dora(marker: str) -> str:
    """ドラ表示牌 → ドラ本体の mjai 牌。"""
    return index_to_tile(next_dora_index(marker))


def dora_tiles(markers: list[str]) -> list[str]:
    return [next_dora(m) for m in markers]


def tile_to_jp(pai: str) -> str:
    """1 枚を日本語表記に。例: "5mr" → "赤5萬", "E" → "東"。"""
    pai = normalize(pai)
    if pai in HONOR_JP:
        return HONOR_JP[pai]
    num = pai[0]
    suit = SUIT_JP.get(pai[1], pai[1])
    prefix = "赤" if is_red_five(pai) else ""
    return f"{prefix}{num}{suit}"


def hand_to_jp(pais: list[str]) -> str:
    """手牌を読みやすい日本語表記に。萬→筒→索→字 の順、各スーツ内は昇順。

    例: ["1m","2m","3m","5pr","E","E"] → "123萬 赤5筒 東東"
    """
    buckets: dict[str, list[str]] = {"m": [], "p": [], "s": [], "z": []}
    for pai in pais:
        n = normalize(pai)
        if n in HONOR_TO_INDEX:
            buckets["z"].append(n)
        else:
            buckets[n[1]].append(n)

    parts: list[str] = []
    for suit in ("m", "p", "s"):
        tiles = sorted(buckets[suit], key=lambda p: (int(p[0]), not is_red_five(p)))
        if not tiles:
            continue
        digits = "".join(("0" if is_red_five(t) else t[0]) for t in tiles)
        parts.append(f"{digits}{SUIT_JP[suit]}")
    if buckets["z"]:
        order = ["E", "S", "W", "N", "P", "F", "C"]
        honors = sorted(buckets["z"], key=order.index)
        parts.append("".join(HONOR_JP[h] for h in honors))
    return " ".join(parts)
