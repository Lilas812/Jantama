"""解析パイプラインのオーケストレーション。

    入力(雀魂URL/ログ) → mjai → Mortal解析 → ミス抽出 → 牌効率計算 → Claude説明
"""

from __future__ import annotations

from typing import Any

from .config import Config
from .explain.explainer import Explainer
from .metrics import compute_metrics
from .models import DecisionPoint, Explanation
from .review.mortal import MortalReviewer
from .sources import PaifuSource, from_input


def select_decisions(
    decisions: list[DecisionPoint], config: Config
) -> list[DecisionPoint]:
    """説明する価値のある局面を選ぶ。

    ミス（推奨と異なる選択）かつ、EV 差がしきい値以上のものを優先。
    EV が取れない場合はミスかどうかだけで判定。損失の大きい順に最大件数まで。
    """
    candidates: list[DecisionPoint] = []
    for dp in decisions:
        if not dp.is_mistake:
            continue
        gap = dp.ev_gap
        if gap is None or gap >= config.mistake_ev_threshold:
            candidates.append(dp)

    candidates.sort(key=lambda d: (d.ev_gap is not None, d.ev_gap or 0.0), reverse=True)
    return candidates[: config.max_explanations]


def analyze(
    source: str | PaifuSource,
    *,
    config: Config | None = None,
    reviewer: Any | None = None,
    explainer: Explainer | None = None,
    actor: int = 0,
) -> list[Explanation]:
    """牌譜を解析し、要改善局面の説明を返す。

    reviewer / explainer は差し替え可能（テスト・他エンジン用）。
    """
    config = config or Config.from_env()
    src = from_input(source, config) if isinstance(source, str) else source
    reviewer = reviewer or MortalReviewer(config, actor=actor)
    explainer = explainer or Explainer(config)

    events = src.load()
    decisions = reviewer.review(events)
    chosen = select_decisions(decisions, config)

    explanations: list[Explanation] = []
    for dp in chosen:
        metrics = compute_metrics(dp)
        explanations.append(explainer.explain(dp, metrics))
    return explanations
