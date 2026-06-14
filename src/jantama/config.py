"""環境変数からの設定読み込み。

秘密情報（APIキー・Discordトークン・雀魂の認証情報）はコードに埋め込まず、
すべて環境変数 / .env 経由で渡す。`.env.example` を参照。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _get(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def _get_float(name: str, default: float) -> float:
    raw = _get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _get_int(name: str, default: int) -> int:
    raw = _get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    # Claude
    anthropic_api_key: str | None = None
    claude_model: str = "claude-opus-4-8"
    claude_effort: str = "medium"
    max_tokens: int = 4000

    # 解析エンジン
    engine: str = "mortal"  # "mortal"（要モデル重み）| "efficiency"（ゼロ設定）
    mjai_reviewer_path: str = "mjai-reviewer"
    mortal_model_path: str | None = None
    mortal_device: str = "cpu"

    # 雀魂
    tensoul_path: str | None = None
    majsoul_access_token: str | None = None

    # Discord
    discord_bot_token: str | None = None

    # しきい値
    mistake_ev_threshold: float = 0.05
    max_explanations: int = 8

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            anthropic_api_key=_get("ANTHROPIC_API_KEY"),
            claude_model=_get("JANTAMA_CLAUDE_MODEL", "claude-opus-4-8"),
            claude_effort=_get("JANTAMA_CLAUDE_EFFORT", "medium"),
            max_tokens=_get_int("JANTAMA_MAX_TOKENS", 4000),
            engine=_get("JANTAMA_ENGINE", "mortal"),
            mjai_reviewer_path=_get("MJAI_REVIEWER_PATH", "mjai-reviewer"),
            mortal_model_path=_get("MORTAL_MODEL_PATH"),
            mortal_device=_get("MORTAL_DEVICE", "cpu"),
            tensoul_path=_get("TENSOUL_PATH"),
            majsoul_access_token=_get("MAJSOUL_ACCESS_TOKEN"),
            discord_bot_token=_get("DISCORD_BOT_TOKEN"),
            mistake_ev_threshold=_get_float("JANTAMA_MISTAKE_EV_THRESHOLD", 0.05),
            max_explanations=_get_int("JANTAMA_MAX_EXPLANATIONS", 8),
        )
