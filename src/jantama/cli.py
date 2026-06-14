"""コマンドラインから牌譜を解析して総評と説明を表示する。

例:
  # 雀魂の牌譜URL（要 変換ツール + Mortal）
  jantama --url "https://game.mahjongsoul.com/?paipu=...";
  # ローカルの mjai ログ（要 Mortal）
  jantama --log game.mjai.json --actor 0
  # 既存の mjai-reviewer 出力から説明だけ生成（Mortal 不要）
  jantama --review-json review.json --actor 0
  # Claude を呼ばず、計算した数値(根拠)だけ表示（API 不要・オフライン確認用）
  jantama --review-json review.json --no-explain
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .config import Config
from .explain.explainer import Explainer
from .explain.prompts import build_user_prompt
from .metrics import compute_metrics
from .models import DecisionPoint, Explanation, ReviewStats
from .pipeline import compute_stats, select_decisions
from .review.parser import parse_review_json
from .sources import from_input


def _load_dotenv(path: str = ".env") -> None:
    """.env があれば環境変数へ読み込む（依存を増やさない簡易版）。"""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _get_decisions(args: argparse.Namespace, config: Config) -> list[DecisionPoint]:
    if args.review_json:
        data = json.loads(Path(args.review_json).read_text(encoding="utf-8"))
        return parse_review_json(data, player_id=args.actor)
    # --url / --log は Mortal による解析が必要
    from .review.mortal import MortalReviewer

    source = from_input(args.url or args.log, config)
    return MortalReviewer(config, actor=args.actor).review(source.load())


def _print_stats(stats: ReviewStats) -> None:
    parts = [f"解析局面: {stats.total_decisions}", f"ミス: {stats.mistakes}"]
    if stats.match_rate is not None:
        parts.append(f"推奨一致率: {stats.match_rate * 100:.1f}%")
    if stats.total_ev_loss is not None:
        parts.append(f"EV損失合計: {stats.total_ev_loss:.2f}")
    print("📊 " + " / ".join(parts))


def _print_explanation(idx: int, exp: Explanation) -> None:
    tag = {"major": "🔴 大きな損", "minor": "🟡 小さな損", "info": "🟢 参考"}.get(
        exp.severity, exp.severity
    )
    print(f"\n{'=' * 60}")
    print(f"{idx}. {exp.header()}  [{tag}]")
    d = exp.decision
    print(f"   あなた: {d.actual_action}  / 推奨: {d.recommended_action}")
    print(f"{'-' * 60}")
    print(exp.text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jantama", description="雀魂 牌譜の言語化解析")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="雀魂の牌譜 URL または paipu ID")
    src.add_argument("--log", help="ローカルの mjai ログ (.json/.jsonl)")
    src.add_argument("--review-json", help="mjai-reviewer の出力 JSON（エンジン解析済み）")
    parser.add_argument("--actor", type=int, default=0, help="解析対象プレイヤー(0-3)")
    parser.add_argument("--model", help="Claude モデル(既定 claude-opus-4-8)")
    parser.add_argument("--effort", help="思考の深さ low|medium|high|max")
    parser.add_argument(
        "--no-explain", action="store_true",
        help="Claude を呼ばず、集計と計算した根拠データのみ表示",
    )
    parser.add_argument(
        "--no-summary", action="store_true", help="総評(サマリ)の生成を省略",
    )
    args = parser.parse_args(argv)

    _load_dotenv()
    config = Config.from_env()
    overrides = {}
    if args.model:
        overrides["claude_model"] = args.model
    if args.effort:
        overrides["claude_effort"] = args.effort
    if overrides:
        from dataclasses import replace

        config = replace(config, **overrides)

    try:
        decisions = _get_decisions(args, config)
        stats = compute_stats(decisions)
        _print_stats(stats)
        chosen = select_decisions(decisions, config)

        if args.no_explain:
            for i, dp in enumerate(chosen, 1):
                metrics = compute_metrics(dp)
                print(f"\n{'=' * 60}\n{i}. {dp.round_wind}{dp.kyoku}局 {dp.junme}巡目")
                print(build_user_prompt(dp, metrics))
            return 0

        explainer = Explainer(config)
        explanations = [explainer.explain(dp, compute_metrics(dp)) for dp in chosen]

        if not args.no_summary:
            print(f"\n{'#' * 60}\n# 総評\n{'#' * 60}")
            print(explainer.summarize(stats, explanations))

        for i, exp in enumerate(explanations, 1):
            _print_explanation(i, exp)
        return 0

    except Exception as exc:  # noqa: BLE001 — CLI の最終防衛線
        print(f"エラー: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
