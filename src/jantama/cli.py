"""コマンドラインから牌譜を解析して説明を表示する。

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
from .models import DecisionPoint
from .pipeline import analyze, select_decisions
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


def _decisions_from_review_json(path: str, actor: int) -> list[DecisionPoint]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return parse_review_json(data, player_id=actor)


def _print_explanation(idx: int, exp) -> None:
    tag = {"major": "🔴 大きな損", "minor": "🟡 小さな損", "info": "🟢 参考"}.get(
        exp.severity, exp.severity
    )
    print(f"\n{'='*60}")
    print(f"{idx}. {exp.header()}  [{tag}]")
    d = exp.decision
    print(f"   あなた: {d.actual_action}  / 推奨: {d.recommended_action}")
    print(f"{'-'*60}")
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
        help="Claude を呼ばず、計算した根拠データのみ表示",
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
        # --review-json は説明層だけを動かす近道
        if args.review_json:
            decisions = _decisions_from_review_json(args.review_json, args.actor)
            chosen = select_decisions(decisions, config)
            if not chosen:
                print("説明すべき局面（推奨と異なる選択）は見つかりませんでした。")
                return 0
            if args.no_explain:
                for i, dp in enumerate(chosen, 1):
                    metrics = compute_metrics(dp)
                    print(f"\n{'='*60}\n{i}. {dp.round_wind}{dp.kyoku}局 {dp.junme}巡目")
                    print(build_user_prompt(dp, metrics))
                return 0
            explainer = Explainer(config)
            for i, dp in enumerate(chosen, 1):
                metrics = compute_metrics(dp)
                _print_explanation(i, explainer.explain(dp, metrics))
            return 0

        # --url / --log は完全パイプライン（Mortal が必要）
        source = args.url or args.log
        if args.no_explain:
            # エンジンだけ動かして根拠を表示
            from .review.mortal import MortalReviewer

            events = from_input(source, config).load()
            decisions = MortalReviewer(config, actor=args.actor).review(events)
            chosen = select_decisions(decisions, config)
            for i, dp in enumerate(chosen, 1):
                metrics = compute_metrics(dp)
                print(f"\n{'='*60}\n{i}. {dp.round_wind}{dp.kyoku}局 {dp.junme}巡目")
                print(build_user_prompt(dp, metrics))
            return 0

        explanations = analyze(source, config=config, actor=args.actor)
        if not explanations:
            print("説明すべき局面（推奨と異なる選択）は見つかりませんでした。")
            return 0
        for i, exp in enumerate(explanations, 1):
            _print_explanation(i, exp)
        return 0

    except Exception as exc:  # noqa: BLE001 — CLI の最終防衛線
        print(f"エラー: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
