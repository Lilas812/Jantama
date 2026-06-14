"""手出し/自摸切りの追跡と河の表示のテスト。"""

from jantama.review import EfficiencyReviewer

_START = {
    "type": "start_kyoku", "bakaze": "E", "kyoku": 1, "honba": 0, "oya": 0,
    "dora_marker": "1z", "scores": [25000, 25000, 25000, 25000],
    "tehais": [
        ["1m", "2m", "3m", "4p", "5p", "6p", "2s", "3s", "4s", "7s", "8s", "9s", "E"],
        [], [], [],
    ],
}


def test_tedashi_tsumogiri_from_explicit_flags():
    events = [
        _START,
        {"type": "tsumo", "actor": 0, "pai": "9m"},
        {"type": "dahai", "actor": 0, "pai": "9m", "tsumogiri": True},
        {"type": "tsumo", "actor": 1, "pai": "1p"},
        {"type": "dahai", "actor": 1, "pai": "W", "tsumogiri": False},   # 下家 手出し
        {"type": "tsumo", "actor": 2, "pai": "2p"},
        {"type": "dahai", "actor": 2, "pai": "2p", "tsumogiri": True},   # 対面 自摸切り
        {"type": "tsumo", "actor": 3, "pai": "3p"},
        {"type": "dahai", "actor": 3, "pai": "N", "tsumogiri": False},   # 上家 手出し
        {"type": "tsumo", "actor": 0, "pai": "5m"},
        {"type": "dahai", "actor": 0, "pai": "5m", "tsumogiri": True},
    ]
    note = EfficiencyReviewer(actor=0).review(events)[-1].river_note
    assert "*=手出し" in note
    assert "下家: 西*" in note      # 手出しは * 付き
    assert "対面: 2筒" in note and "対面: 2筒*" not in note  # 自摸切りは素
    assert "上家: 北*" in note


def test_tsumogiri_derived_when_flag_absent():
    # tsumogiri フラグが無くても、ツモ牌と一致すれば自摸切りと判定する
    events = [
        _START,
        {"type": "tsumo", "actor": 0, "pai": "9m"},
        {"type": "dahai", "actor": 0, "pai": "9m"},
        {"type": "tsumo", "actor": 1, "pai": "5p"},
        {"type": "dahai", "actor": 1, "pai": "5p"},   # ツモ牌5pを切る→自摸切り(導出)
        {"type": "tsumo", "actor": 2, "pai": "3s"},
        {"type": "dahai", "actor": 2, "pai": "W"},     # ツモ3sでないW→手出し(導出)
        {"type": "tsumo", "actor": 3, "pai": "1m"},
        {"type": "dahai", "actor": 3, "pai": "1m"},
        {"type": "tsumo", "actor": 0, "pai": "2m"},
        {"type": "dahai", "actor": 0, "pai": "2m"},
    ]
    note = EfficiencyReviewer(actor=0).review(events)[-1].river_note
    assert "5筒*" not in note      # 5筒は自摸切り（無印）
    assert "対面: 西*" in note      # W は手出し（導出）
