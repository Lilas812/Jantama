"""牌譜の入力源: 雀魂の URL/ログ や ローカルの mjai ログから mjai イベント列を得る。"""

from .base import PaifuSource, PaifuUnavailableError
from .local import LocalLogSource
from .mahjong_soul import (
    MahjongSoulSource,
    from_input,
    is_majsoul_input,
    parse_paipu_url,
)

__all__ = [
    "PaifuSource",
    "PaifuUnavailableError",
    "LocalLogSource",
    "MahjongSoulSource",
    "parse_paipu_url",
    "is_majsoul_input",
    "from_input",
]
