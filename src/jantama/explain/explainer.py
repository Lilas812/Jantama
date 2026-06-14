"""Claude を用いて DecisionPoint の「なぜ」を生成する。

公式 anthropic Python SDK を使用。モデル既定は claude-opus-4-8。
推論を要するタスクなので adaptive thinking + effort を用いる。

`client` を注入できるようにしてあり、テストではフェイククライアントを渡せる。
"""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..models import DecisionPoint, Explanation, Metrics
from .prompts import SYSTEM_PROMPT, build_user_prompt


class ExplainerError(RuntimeError):
    pass


class Explainer:
    def __init__(self, config: Config | None = None, client: Any | None = None) -> None:
        self.config = config or Config.from_env()
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            if not self.config.anthropic_api_key:
                raise ExplainerError(
                    "ANTHROPIC_API_KEY が未設定です。説明の生成には API キーが必要です。"
                )
            import anthropic

            self._client = anthropic.Anthropic(api_key=self.config.anthropic_api_key)
        return self._client

    def explain(self, dp: DecisionPoint, metrics: Metrics) -> Explanation:
        prompt = build_user_prompt(dp, metrics)
        response = self.client.messages.create(
            model=self.config.claude_model,
            max_tokens=self.config.max_tokens,
            system=SYSTEM_PROMPT,
            thinking={"type": "adaptive"},
            output_config={"effort": self.config.claude_effort},
            messages=[{"role": "user", "content": prompt}],
        )
        text = self._extract_text(response)
        return Explanation(
            decision=dp,
            metrics=metrics,
            text=text,
            severity=_severity(dp, metrics, self.config.mistake_ev_threshold),
        )

    @staticmethod
    def _extract_text(response: Any) -> str:
        if getattr(response, "stop_reason", None) == "refusal":
            return "（安全フィルタにより、この局面の説明を生成できませんでした。）"
        parts = [
            block.text
            for block in getattr(response, "content", [])
            if getattr(block, "type", None) == "text"
        ]
        return "\n".join(p for p in parts if p).strip() or "（説明を生成できませんでした。）"


def _severity(dp: DecisionPoint, metrics: Metrics, threshold: float) -> str:
    """損失の大きさからタグ付け。EV 差を最優先、無ければ向聴/受け入れで近似。"""
    gap = dp.ev_gap
    if gap is not None:
        if gap >= threshold * 3:
            return "major"
        if gap >= threshold:
            return "minor"
        return "info"
    # EV が無い場合のフォールバック
    sa, sr = metrics.shanten_after_actual, metrics.shanten_after_recommended
    if sa is not None and sr is not None and sa > sr:
        return "major"  # 向聴を損している
    ua, ur = metrics.ukeire_after_actual, metrics.ukeire_after_recommended
    if ua is not None and ur is not None and ur - ua >= 4:
        return "minor"
    return "info"
