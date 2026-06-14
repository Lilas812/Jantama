"""説明生成層: 確定した数値を根拠に Claude が「なぜ」を日本語化する。"""

from .explainer import Explainer
from .prompts import SYSTEM_PROMPT, build_user_prompt

__all__ = ["Explainer", "SYSTEM_PROMPT", "build_user_prompt"]
