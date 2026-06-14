"""じゃん玉 — 雀魂の牌譜を解析し「なぜその打牌が良いのか」を日本語で説明するツール。

パイプライン:
    牌譜/局面 → 解析エンジン(Mortal) → 数値の計算(向聴・受け入れ) → Claudeで言語化
"""

from .models import DecisionPoint, Explanation, Metrics

__all__ = ["DecisionPoint", "Explanation", "Metrics"]
__version__ = "0.1.0"
