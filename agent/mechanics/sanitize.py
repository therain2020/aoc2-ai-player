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


def sanitize_actions(actions: list[dict], st: dict, fail_provinces=()) -> list[dict]:
    if not isinstance(actions, list):
        return []
    # 被占省（true_owner≠我，引擎禁征兵/投资）+ 已失败省（失败反馈闭环）
    occupied = {int(x.get("prov")) for x in (st.get("occupied_by_me") or [])} | set(
        int(p) for p in (fail_provinces or []))
    fronts: dict[tuple[int, int], int] = {}
    for f in st.get("front_lines") or []:
        try:
            fronts[(int(f.get("from")), int(f.get("to")))] = int(f.get("my_units") or 0)
        except (TypeError, ValueError):
            continue
    out: list[dict] = []
    declared = 0
    recruits = 0
    # 金<500 = 破产前置线：禁止再募兵（防空耗金库；引擎 AI 同款 0.5K 底线）
    broke = float(st.get("money") or 0) < 500
    for a in actions:
        if not isinstance(a, dict) or "action" not in a:
            continue
        n = a.get("action")
        if n == "move_army":
            frm = int(a.get("from_province", -1))
            to = int(a.get("to_province", -1))
            if frm == to:
                continue
            mine = set(int(p) for p in (st.get("my_provinces") or []))
            key = (frm, to)
            if key in fronts:
                own = fronts[key]
                a["count"] = max(10, min(int(a.get("count") or 10), own))
                out.append(a)                   # 进攻：仅前线对，兵≥10 ≤省兵
            elif frm in mine and to in mine:
                a["count"] = max(1, int(a.get("count") or 1))
                out.append(a)                   # 集结：我方省→我方省（调兵上战线，放行）
            else:
                continue                        # 越界/未知对：丢弃
        elif n == "declare_war":
            if declared >= 1:
                continue                       # 每回合至多一次新宣战
            declared += 1
            out.append(a)
        elif n == "recruit_army":
            if broke or recruits >= 2:         # 破产禁募 / 每回合至多 2 批
                continue
            if int(a.get("province_id") or -1) in occupied:
                continue                        # 被占/失败恢复省不再征兵（引擎也会拒）
            recruits += 1
            out.append(a)
        else:
            out.append(a)
    return out
