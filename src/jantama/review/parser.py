"""mjai-reviewer / Mortal の出力 JSON を DecisionPoint へ正規化する。

mjai-reviewer (https://github.com/Equim-chan/mjai-reviewer) の `--json` 出力を
想定。バージョンによりスキーマが揺れるため、ここを唯一の調整ポイントとして
緩めにパースする。想定する大まかな形:

    {
      "player_id": 0,
      "review": {
        "kyokus": [
          {
            "kyoku": 0,            # 0-3=東1-4, 4-7=南1-4
            "honba": 0,
            "dora_markers": ["2m"],
            "entries": [
              {
                "junme": 3,
                "tiles": ["1m", ...],          # 打牌前の手牌(mjai牌)
                "last_draw": "5p",
                "actual": "1m",                # 牌 or mjai アクション
                "expected": "9p",
                "details": [
                  {"action": {"type":"dahai","pai":"9p"}, "prob":0.6, "q_value":12.3},
                  ...
                ],
                "shanten": 1
              }
            ]
          }
        ]
      }
    }

`q_value` を EV、`prob` を方策確率として扱う。
"""

from __future__ import annotations

from ..models import DecisionPoint

_BAKAZE = ["東", "南", "西", "北"]
_JIKAZE = ["東", "南", "西", "北"]


def parse_review_json(data: dict, player_id: int | None = None) -> list[DecisionPoint]:
    """mjai-reviewer の JSON 全体を DecisionPoint のリストへ変換する。"""
    review = data.get("review", data)
    if player_id is None:
        player_id = data.get("player_id", review.get("player_id", 0))

    kyokus = review.get("kyokus") or review.get("kyoku_reviews") or []
    points: list[DecisionPoint] = []
    for kyoku in kyokus:
        points.extend(_parse_kyoku(kyoku, player_id))
    return points


def _parse_kyoku(kyoku: dict, player_id: int) -> list[DecisionPoint]:
    k = kyoku.get("kyoku", 0)
    bakaze = _BAKAZE[(k // 4) % 4]
    kyoku_num = (k % 4) + 1
    honba = kyoku.get("honba", 0)
    dora_markers = list(kyoku.get("dora_markers") or kyoku.get("doras") or [])
    oya = k % 4
    seat_wind = _JIKAZE[(player_id - oya) % 4]
    is_dealer = player_id == oya

    entries = kyoku.get("entries") or kyoku.get("details") or []
    out: list[DecisionPoint] = []
    for entry in entries:
        dp = _parse_entry(
            entry,
            bakaze=bakaze,
            kyoku_num=kyoku_num,
            honba=honba,
            player_id=player_id,
            seat_wind=seat_wind,
            is_dealer=is_dealer,
            dora_markers=dora_markers,
        )
        if dp is not None:
            out.append(dp)
    return out


def _parse_entry(
    entry: dict,
    *,
    bakaze: str,
    kyoku_num: int,
    honba: int,
    player_id: int,
    seat_wind: str,
    is_dealer: bool,
    dora_markers: list[str],
) -> DecisionPoint | None:
    hand = list(entry.get("tiles") or entry.get("hand") or [])
    if not hand:
        return None

    actual_raw = entry.get("actual")
    expected_raw = entry.get("expected") or entry.get("recommended")

    details = entry.get("details") or entry.get("candidates") or []
    candidates: list[tuple[str, float]] = []
    actual_ev = recommended_ev = None
    prob_actual = prob_recommended = None

    actual_action = _action_label(actual_raw)
    recommended_action = _action_label(expected_raw)

    for d in details:
        label = _action_label(d.get("action", d.get("type")))
        ev = _num(d.get("q_value", d.get("ev")))
        prob = _num(d.get("prob", d.get("probability")))
        if ev is not None:
            candidates.append((label, ev))
        if label and label == actual_action:
            actual_ev = ev
            prob_actual = prob
        if label and label == recommended_action:
            recommended_ev = ev
            prob_recommended = prob

    # details が EV 降順でない場合に備え、推奨が未取得なら最良候補を採用
    if recommended_action == "" and candidates:
        best = max(candidates, key=lambda c: c[1])
        recommended_action, recommended_ev = best[0], best[1]

    return DecisionPoint(
        round_wind=bakaze,
        kyoku=kyoku_num,
        honba=honba,
        seat=player_id,
        seat_wind=seat_wind,
        is_dealer=is_dealer,
        junme=entry.get("junme", 0),
        hand=hand,
        drawn_tile=entry.get("last_draw") or entry.get("tsumo"),
        dora_markers=dora_markers,
        melds=list(entry.get("melds") or []),
        actual_action=actual_action,
        recommended_action=recommended_action,
        actual_ev=actual_ev,
        recommended_ev=recommended_ev,
        prob_actual=prob_actual,
        prob_recommended=prob_recommended,
        candidates=candidates,
        scores=entry.get("scores"),
    )


def _action_label(action: object) -> str:
    """mjai アクション(または牌文字列) を行動ラベルへ。

    打牌は牌そのものを返し、metrics 側でそのまま打牌として扱えるようにする。
    """
    if action is None:
        return ""
    if isinstance(action, str):
        return action
    if isinstance(action, dict):
        atype = action.get("type", "")
        if atype == "dahai":
            return str(action.get("pai", ""))
        if atype == "reach" or atype == "riichi":
            return "リーチ"
        if atype in ("chi", "pon", "kan", "ankan", "daiminkan", "kakan"):
            label = {"chi": "チー", "pon": "ポン", "kan": "カン",
                     "ankan": "暗槓", "daiminkan": "大明槓", "kakan": "加槓"}[atype]
            pai = action.get("pai", "")
            return f"{label} {pai}".strip()
        if atype == "hora" or atype == "agari":
            return "和了"
        if atype == "none" or atype == "skip":
            return "スルー"
        return atype
    return str(action)


def _num(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
