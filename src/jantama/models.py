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
    # 場に見えている牌（全員の河 + 副露 + ドラ表示）。自分の手牌は含まない。
    # 受け入れの残り枚数を正確に数えるために使う。空なら ドラ表示のみで近似。
    visible_tiles: list[str] = field(default_factory=list)
    # 自分の副露を構成する実牌（ドラ集計用）。空なら副露牌のドラは未集計。
    meld_tiles: list[str] = field(default_factory=list)

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
    note: str = ""  # 推奨の基準などの備考
    safety_note: str = ""  # 押し引き(他家リーチ・現物)に関する情報
    river_note: str = ""  # 他家の河（手出し/自摸切り付き）の読み材料
    wait_note: str = ""  # 他家リーチの待ち推定（両面候補など）

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

    dora_in_hand: int = 0  # 手牌中のドラ枚数（赤含む。副露牌は未集計）
    num_melds: int = 0  # 副露(鳴き)の数。概要牌の枚数から判定
    available: bool = True  # 入力が不正で計算できない場合のみ False
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


@dataclass
class ReviewStats:
    """牌譜全体（解析対象プレイヤー）の集計。サマリの土台になる数値。"""

    total_decisions: int = 0  # エンジンが評価した意思決定の総数
    mistakes: int = 0  # 推奨と異なった回数
    total_ev_loss: float | None = None  # EV 損失の合計（EV が取れた場合）

    @property
    def matches(self) -> int:
        return self.total_decisions - self.mistakes

    @property
    def match_rate(self) -> float | None:
        """推奨一致率（0.0〜1.0）。解析局面が無ければ None。"""
        if self.total_decisions <= 0:
            return None
        return self.matches / self.total_decisions


@dataclass
class GameReport:
    """1 つの牌譜の解析結果（個別指摘 + 全体サマリ）。"""

    stats: ReviewStats
    explanations: list[Explanation] = field(default_factory=list)
    summary: str = ""

