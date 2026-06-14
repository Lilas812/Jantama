"""解析パイプラインのオーケストレーション。

    入力(雀魂URL/ログ) → mjai → Mortal解析 → ミス抽出 → 牌効率計算 → Claude説明
    さらに対局全体を集計して総評(サマリ)を生成する。
"""

from __future__ import annotations

from typing import Any

from .config import Config
from .explain.explainer import Explainer
from .metrics import compute_metrics
from .models import DecisionPoint, Explanation, GameReport, ReviewStats
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


def compute_stats(decisions: list[DecisionPoint]) -> ReviewStats:
    """全意思決定からの集計（一致率・EV 損失合計）。"""
    total = len(decisions)
    mistakes = sum(1 for d in decisions if d.is_mistake)
    gaps = [d.ev_gap for d in decisions if d.is_mistake and d.ev_gap is not None]
    total_ev_loss = round(sum(gaps), 3) if gaps else None
    return ReviewStats(total_decisions=total, mistakes=mistakes, total_ev_loss=total_ev_loss)


def _explain_decisions(
    decisions: list[DecisionPoint], explainer: Explainer, config: Config
) -> list[Explanation]:
    explanations: list[Explanation] = []
    for dp in select_decisions(decisions, config):
        explanations.append(explainer.explain(dp, compute_metrics(dp)))
    return explanations


def _resolve(
    source: str | PaifuSource,
    config: Config | None,
    reviewer: Any | None,
    explainer: Explainer | None,
    actor: int,
) -> tuple[Config, list[DecisionPoint], Explainer]:
    config = config or Config.from_env()
    src = from_input(source, config) if isinstance(source, str) else source
    reviewer = reviewer or MortalReviewer(config, actor=actor)
    explainer = explainer or Explainer(config)
    decisions = reviewer.review(src.load())
    return config, decisions, explainer


def analyze(
    source: str | PaifuSource,
    *,
    config: Config | None = None,
    reviewer: Any | None = None,
    explainer: Explainer | None = None,
    actor: int = 0,
) -> list[Explanation]:
    """牌譜を解析し、要改善局面の説明を返す（サマリ無し）。"""
    config, decisions, explainer = _resolve(source, config, reviewer, explainer, actor)
    return _explain_decisions(decisions, explainer, config)


def analyze_report(
    source: str | PaifuSource,
    *,
    config: Config | None = None,
    reviewer: Any | None = None,
    explainer: Explainer | None = None,
    actor: int = 0,
    summarize: bool = True,
) -> GameReport:
    """牌譜を解析し、集計・個別指摘・総評をまとめたレポートを返す。"""
    config, decisions, explainer = _resolve(source, config, reviewer, explainer, actor)
    stats = compute_stats(decisions)
    explanations = _explain_decisions(decisions, explainer, config)
    summary = explainer.summarize(stats, explanations) if summarize else ""
    return GameReport(stats=stats, explanations=explanations, summary=summary)
