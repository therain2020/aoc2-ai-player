"""Reserve discipline (FR-017⑤ / SC-011) — dynamic gold floor + military line.

gold_floor = 3 × per-turn net income (income < 0 -> use trailing 5-turn mean ×3,
floor >= 0). A decision must not knowingly breach it; when breached the context
injects "fix income / cut spend" as top priority.
"""
from __future__ import annotations

RESERVE_MULT = 3
TRAILING = 5
MILITARY_HINT = 1.2
MILITARY_FORCE = 1.5


def gold_floor(st: dict | None, trailing_income: list[float] | None = None) -> float:
    """3× net per-turn income; fall back to trailing-mean if income is non-positive."""
    inc = (st or {}).get("income") or {}
    net = inc.get("gold")
    if isinstance(net, (int, float)) and net > 0:
        return round(net * RESERVE_MULT, 1)
    if trailing_income:
        vals = [v for v in trailing_income if isinstance(v, (int, float))]
        if vals:
            mean = sum(vals) / len(vals)
            if mean > 0:
                return round(mean * RESERVE_MULT, 1)
    return 0.0


def reserve_guard(st: dict, floor: float) -> dict:
    """(breached, note) — SC-011 judge; caller records the breach in turns.jsonl."""
    try:
        gold = float(st.get("money") or 0)
    except (TypeError, ValueError):
        return {"breached": False, "note": ""}
    if floor > 0 and gold < floor:
        return {"breached": True,
                "note": f"储备线: 金 {gold:.0f} < 3×净收入 {floor:.0f}——本回合必须修复收入/收缩开支",
                "floor": floor, "gold": gold}
    return {"breached": False, "note": ""}


def reserve_line(st: dict | None, trailing_income: list[float] | None = None) -> str:
    """One-line DecisionContext hint (FR-018 concise)."""
    floor = gold_floor(st, trailing_income)
    g = reserve_guard(st, floor)
    if g["breached"]:
        return g["note"]
    gold = (st or {}).get("money")
    return f"储备线: 金{gold} ≥ 3×净收入 {floor:.0f} ✓（保留线未击穿）"
