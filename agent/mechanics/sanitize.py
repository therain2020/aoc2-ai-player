"""Action sanitizer — harness guard before execution.

2026-08-29 (user bug report): the LLM emitted moves to non-adjacent provinces
and declared war on two neighbors in one turn (T3 disaster). The sanitizer
constrains actions to engine-legal fields:
  - move_army  only on real front-line pairs (from/to ∈ front_lines),
               count ≥ 10 and ≤ the province's own units
  - declare_war at most one per turn (additional wars is a strategic decision
               for a later turn, not a single-turn burst)
Everything else passes through.
"""
from __future__ import annotations


def sanitize_actions(actions: list[dict], st: dict) -> list[dict]:
    if not isinstance(actions, list):
        return []
    fronts: dict[tuple[int, int], int] = {}
    for f in st.get("front_lines") or []:
        try:
            fronts[(int(f.get("from")), int(f.get("to")))] = int(f.get("my_units") or 0)
        except (TypeError, ValueError):
            continue
    out: list[dict] = []
    declared = 0
    recruits = 0
    broke = float(st.get("money") or 0) < 0     # 破产：禁止再募兵（止血）
    for a in actions:
        if not isinstance(a, dict) or "action" not in a:
            continue
        n = a.get("action")
        if n == "move_army":
            key = (int(a.get("from_province", -1)), int(a.get("to_province", -1)))
            if key not in fronts:
                continue                       # 非真实前线对：丢弃
            own = fronts[key]
            a["count"] = max(10, min(int(a.get("count") or 10), own))
            out.append(a)
        elif n == "declare_war":
            if declared >= 1:
                continue                       # 每回合至多一次新宣战
            declared += 1
            out.append(a)
        elif n == "recruit_army":
            if broke or recruits >= 2:         # 破产禁募 / 每回合至多 2 批
                continue
            recruits += 1
            out.append(a)
        else:
            out.append(a)
    return out
