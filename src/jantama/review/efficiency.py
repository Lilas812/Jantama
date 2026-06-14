"""Mortal 不要・ゼロ設定で動く「牌効率＋押し引き」レビューア。

mjai のゲームログを直接読み（mjai_state.iter_decisions）、各局面で対象プレイヤーの
手牌を復元し、自前の向聴・受け入れ計算で「受け入れ最大（向聴最小）」の打牌を
推奨として算出する。河・副露・ドラを考慮して受け入れ枚数を正確に数える。

押し引き: 他家がリーチ中で、実際の打牌が現物(安全)・効率最善が危険なら、その
ベタ降りは妥当とみなし効率ミスとして扱わない。現物情報は説明にも添える。

注意: 役・打点までは評価しない近似だが、外部部品なしで生の牌譜を端から解析でき、
明確な効率損失や安全牌情報を伴うコーチングが可能。
"""

from __future__ import annotations

from ..config import Config
from ..metrics.shanten import calc_shanten, calc_ukeire, count_dora
from ..models import DecisionPoint
from ..tiles import index_to_tile, normalize, tile_to_index, to_34_array, without_tile
from .danger import analyze_push_fold
from .mjai_state import DecisionContext, format_rivers, iter_decisions

_EFFICIENCY_NOTE = "牌効率ベースの推奨（役・打点は未考慮）"


class EfficiencyReviewer:
    """受け入れ最大の打牌を推奨とし、押し引きも加味するエンジン不要のレビューア。"""

    def __init__(self, config: Config | None = None, actor: int = 0,
                 min_ukeire_drop: int = 4) -> None:
        self.config = config or Config.from_env()
        self.actor = actor
        self.min_ukeire_drop = min_ukeire_drop

    def review(self, mjai_events: list[dict]) -> list[DecisionPoint]:
        out: list[DecisionPoint] = []
        for ctx in iter_decisions(mjai_events, self.actor):
            dp = self._evaluate(ctx)
            if dp is not None:
                out.append(dp)
        return out

    def _evaluate(self, ctx: DecisionContext) -> DecisionPoint | None:
        open_hand = bool(ctx.meld_descs)
        allow_special = not open_hand
        base_visible = to_34_array(ctx.visible_tiles)

        evals = self._eval_discards(ctx.hand, base_visible, allow_special)
        if not evals:
            return None
        best_idx, (best_sh, best_uk) = min(
            evals.items(), key=lambda kv: (kv[1][0], -kv[1][1])
        )
        actual_pai = normalize(ctx.discard)
        actual_idx = tile_to_index(actual_pai)
        actual_sh, actual_uk = evals.get(actual_idx, (best_sh, best_uk))

        # 牌効率ベースの損失（リーチ無しの基本判定）
        is_loss = actual_sh > best_sh or (
            actual_sh == best_sh and best_uk - actual_uk >= self.min_ukeire_drop
        )
        recommended_idx = best_idx if is_loss else actual_idx

        # リーチがあれば押し引き（危険度＋テンパイ）で上書き判断
        pf = analyze_push_fold(
            ctx, to_34_array(ctx.hand), evals, best_idx, actual_idx,
            count_dora(ctx.hand, ctx.dora_markers), self.min_ukeire_drop,
        )
        if pf is not None:
            is_loss = pf.is_mistake
            recommended_idx = pf.recommended_idx if is_loss else actual_idx
            safety_note = pf.note
        else:
            safety_note = ""

        # is_mistake は actual≠recommended で決まるため、損でない時は推奨=実打に揃える
        recommended = index_to_tile(recommended_idx) if recommended_idx != actual_idx else actual_pai

        return DecisionPoint(
            round_wind=ctx.bakaze,
            kyoku=ctx.kyoku,
            honba=ctx.honba,
            seat=ctx.actor,
            seat_wind=ctx.seat_wind,
            is_dealer=ctx.is_dealer,
            junme=ctx.junme,
            hand=list(ctx.hand),
            drawn_tile=ctx.drawn,
            dora_markers=list(ctx.dora_markers),
            melds=list(ctx.meld_descs),
            visible_tiles=list(ctx.visible_tiles),
            meld_tiles=list(ctx.meld_tiles),
            actual_action=actual_pai,
            recommended_action=recommended,
            scores=ctx.scores,
            note=_EFFICIENCY_NOTE,
            safety_note=safety_note,
            river_note=format_rivers(ctx),
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
