"""Mortal 不要・ゼロ設定で動く「牌効率」レビューア。

mjai のゲームログを直接読み、各局面で対象プレイヤーの手牌を復元し、自前の
向聴・受け入れ計算で「受け入れ最大（向聴最小）」の打牌を推奨として算出する。
全員の河・副露・ドラ表示を「場に見えている牌」として追跡し、受け入れの残り
枚数を正確に数える。

注意: これは純粋な牌効率の近似であり、押し引き・役・打点・安全度は考慮しない。
強さでは Mortal に劣るが、外部部品なしで生の牌譜を端から解析できるのが利点。
明確な効率の損失（向聴が悪化 / 受け入れが大きく減少）のみを「ミス」として扱う。
"""

from __future__ import annotations

from ..config import Config
from ..metrics.shanten import calc_shanten, calc_ukeire
from ..models import DecisionPoint
from ..tiles import index_to_tile, normalize, tile_to_index, to_34_array, without_tile

_BAKAZE = {"E": "東", "S": "南", "W": "西", "N": "北"}
_JIKAZE = ["東", "南", "西", "北"]
_FURO_LABEL = {
    "pon": "ポン", "chi": "チー", "daiminkan": "大明槓",
    "ankan": "暗槓", "kakan": "加槓",
}
_EFFICIENCY_NOTE = "牌効率ベースの推奨（押し引き・役・安全度は未考慮）"


class EfficiencyReviewer:
    """受け入れ最大の打牌を推奨とする、エンジン不要のレビューア。"""

    def __init__(self, config: Config | None = None, actor: int = 0,
                 min_ukeire_drop: int = 4) -> None:
        self.config = config or Config.from_env()
        self.actor = actor
        self.min_ukeire_drop = min_ukeire_drop

    def review(self, mjai_events: list[dict]) -> list[DecisionPoint]:
        hands: list[list[str]] = [[], [], [], []]
        meld_descs: list[list[str]] = [[], [], [], []]
        reached = [False, False, False, False]
        last_tsumo: list[str | None] = [None, None, None, None]
        junme = [0, 0, 0, 0]
        dora_markers: list[str] = []
        visible: list[str] = []  # 河 + 副露 + ドラ表示（自分の手牌は含まない）
        ctx: dict = {}
        points: list[DecisionPoint] = []

        for ev in mjai_events:
            t = ev.get("type")
            if t == "start_kyoku":
                tehais = ev.get("tehais") or [[], [], [], []]
                for a in range(4):
                    hands[a] = list(tehais[a])
                    meld_descs[a] = []
                    reached[a] = False
                    last_tsumo[a] = None
                    junme[a] = 0
                dora_markers = [ev["dora_marker"]] if ev.get("dora_marker") else []
                visible = list(dora_markers)
                ctx = {
                    "bakaze": _BAKAZE.get(ev.get("bakaze", "E"), "東"),
                    "kyoku": ev.get("kyoku", 1),
                    "honba": ev.get("honba", 0),
                    "oya": ev.get("oya", 0),
                    "scores": ev.get("scores"),
                }
            elif t == "dora":
                if ev.get("dora_marker"):
                    dora_markers.append(ev["dora_marker"])
                    visible.append(ev["dora_marker"])
            elif t == "tsumo":
                a = ev["actor"]
                hands[a].append(ev["pai"])
                last_tsumo[a] = ev["pai"]
                junme[a] += 1
            elif t == "dahai":
                a = ev["actor"]
                if a == self.actor and not reached[a]:
                    dp = self._make_decision(ev, hands[a], last_tsumo[a], dora_markers,
                                              meld_descs[a], junme[a], ctx, visible)
                    if dp is not None:
                        points.append(dp)
                hands[a] = without_tile(hands[a], ev["pai"])
                last_tsumo[a] = None
                visible.append(ev["pai"])  # 河に出た＝場に見えた
            elif t in ("pon", "chi", "daiminkan", "ankan"):
                a = ev["actor"]
                for c in ev.get("consumed", []):  # 手牌から晒された牌
                    hands[a] = without_tile(hands[a], c)
                    visible.append(c)
                meld_descs[a].append(_FURO_LABEL.get(t, "副露"))
                last_tsumo[a] = None
            elif t == "kakan":
                a = ev["actor"]
                pai = ev.get("pai", "")
                hands[a] = without_tile(hands[a], pai)
                if pai:
                    visible.append(pai)
                last_tsumo[a] = None
            elif t == "reach_accepted":
                reached[ev["actor"]] = True
        return points

    def _make_decision(self, ev, hand, drawn, dora_markers, meld_descs, junme, ctx, visible):
        if len(hand) % 3 != 2:  # 打牌前(3n+2)でなければスキップ（槓直後など）
            return None
        open_hand = bool(meld_descs)
        allow_special = not open_hand
        base_visible = to_34_array(visible)

        evals = self._eval_discards(hand, base_visible, allow_special)
        if not evals:
            return None
        best_idx, (best_sh, best_uk) = min(
            evals.items(), key=lambda kv: (kv[1][0], -kv[1][1])
        )
        actual_pai = normalize(ev["pai"])
        actual_idx = tile_to_index(actual_pai)
        actual_sh, actual_uk = evals.get(actual_idx, (best_sh, best_uk))

        is_loss = actual_sh > best_sh or (
            actual_sh == best_sh and best_uk - actual_uk >= self.min_ukeire_drop
        )
        recommended = index_to_tile(best_idx) if is_loss else actual_pai

        oya = ctx.get("oya", 0)
        return DecisionPoint(
            round_wind=ctx.get("bakaze", "東"),
            kyoku=ctx.get("kyoku", 1),
            honba=ctx.get("honba", 0),
            seat=self.actor,
            seat_wind=_JIKAZE[(self.actor - oya) % 4],
            is_dealer=self.actor == oya,
            junme=junme,
            hand=list(hand),
            drawn_tile=drawn,
            dora_markers=list(dora_markers),
            melds=list(meld_descs),
            visible_tiles=list(visible),
            actual_action=actual_pai,
            recommended_action=recommended,
            scores=ctx.get("scores"),
            note=_EFFICIENCY_NOTE,
        )

    @staticmethod
    def _eval_discards(hand, base_visible34, allow_special) -> dict[int, tuple[int, int]]:
        results: dict[int, tuple[int, int]] = {}
        for p in hand:
            idx = tile_to_index(p)
            if idx in results:
                continue
            rest = without_tile(hand, p)
            arr = to_34_array(rest)
            sh = calc_shanten(arr, allow_special)
            visible = list(base_visible34)
            visible[idx] += 1  # 切る牌も場に出た1枚として控除
            uk, _ = calc_ukeire(arr, visible, allow_special)
            results[idx] = (sh, uk)
        return results
