"""パイプライン全体で受け渡すデータ構造。

DecisionPoint   : 1 つの意思決定局面（手牌・ドラ・実際の選択・エンジンの推奨）
Metrics         : その局面について計算した数値（向聴・受け入れ・ドラ枚数）
Explanation     : Claude が生成した「なぜ」の説明文
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DecisionPoint:
    """1 局のある巡目における、あるプレイヤーの打牌判断。"""

    # 局の情報
    round_wind: str  # "東" / "南"
    kyoku: int  # 1〜4（その風の何局目か）
    honba: int
    seat: int  # 0=自家, 1=下家, 2=対面, 3=上家（牌譜起点）
    seat_wind: str  # 自風 "東"/"南"/"西"/"北"
    is_dealer: bool
    junme: int  # 巡目

    # 局面
    hand: list[str]  # 打牌前の手牌（ツモ牌を含む。mjai 牌）
    drawn_tile: str | None  # 直前のツモ牌
    dora_markers: list[str]  # ドラ表示牌
    melds: list[str] = field(default_factory=list)  # 副露（人間可読の説明文）

    # 選択
    actual_action: str = ""  # 実際の選択（例: 打牌 "1p" / "リーチ" など）
    recommended_action: str = ""  # エンジンの推奨

    # エンジンの評価値（取得できた場合）
    actual_ev: float | None = None
    recommended_ev: float | None = None
    prob_actual: float | None = None  # 方策の確率
    prob_recommended: float | None = None
    candidates: list[tuple[str, float]] = field(default_factory=list)  # (選択, 価値)

    # 補足情報
    scores: list[int] | None = None  # 各家の点棒
    note: str = ""  # 牌譜由来の備考（鳴き判断など）

    @property
    def ev_gap(self) -> float | None:
        """推奨と実際の価値差。大きいほど損失が大きい。"""
        if self.actual_ev is None or self.recommended_ev is None:
            return None
        return self.recommended_ev - self.actual_ev

    @property
    def is_mistake(self) -> bool:
        """実際の選択がエンジンの推奨と異なるか。"""
        if not self.recommended_action:
            return False
        return self.actual_action != self.recommended_action


@dataclass
class Metrics:
    """DecisionPoint について自前計算した牌効率の数値。"""

    shanten_before: int | None = None  # 打牌前の向聴（-1=和了, 0=聴牌）
    # 実際の打牌後
    shanten_after_actual: int | None = None
    ukeire_after_actual: int | None = None  # 受け入れ枚数
    ukeire_tiles_actual: list[str] = field(default_factory=list)
    # 推奨打牌後
    shanten_after_recommended: int | None = None
    ukeire_after_recommended: int | None = None
    ukeire_tiles_recommended: list[str] = field(default_factory=list)

    dora_in_hand: int = 0  # 手牌中のドラ枚数（赤含む）
    available: bool = True  # 副露等で精密計算できない場合 False
    reason_unavailable: str = ""


@dataclass
class Explanation:
    """1 つの局面に対する説明（最終成果物）。"""

    decision: DecisionPoint
    metrics: Metrics
    text: str  # Claude が生成した日本語の説明
    severity: str = "info"  # "info" / "minor" / "major"（損失の大きさ）

    def header(self) -> str:
        d = self.decision
        return f"【{d.round_wind}{d.kyoku}局 {d.junme}巡目】"
