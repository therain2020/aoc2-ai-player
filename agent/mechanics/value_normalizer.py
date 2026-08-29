"""Engine-cost-aware value normalization (2026-08-29 user critique).

The LLM writes scalar params (recruit 200, invest 500, gift 300) without
looking at the ledger — with a 67k coffer recruit 200 wastes the per-batch
move-point cost (COST_OF_RECRUIT is per PROVINCE, not per soldier) and invest
500 under-uses the coffer. This normalizes params against the state right
before execution:

  recruit_army : count ~= money-derived target (engine clamps to recruitable
                 army and money/persoldier limits)
  invest*      : gold ~= 15% of coffer (engine clamps to invest_MaxEconomy_Gold)
  gift/buy_war/coalition/support: gold ~= 5-10% of coffer
"""
from __future__ import annotations


def _money(st: dict) -> int:
    try:
        return max(0, int(st.get("money") or 0))
    except (TypeError, ValueError):
        return 0


def _scale(gold: int, lo: int, hi: int) -> int:
    if gold <= 0:
        return lo
    v = max(lo, min(gold, hi))
    return int(v // 100 * 100)


def normalize_values(actions: list[dict], st: dict) -> list[dict]:
    money = _money(st)
    for a in actions or []:
        name = a.get("action")
        if name in ("invest", "invest_dev"):
            a["gold"] = _scale(int(money * 0.15), 300, 50000)
        elif name == "recruit_army":
            # engine: one COST_OF_RECRUIT per province-batch, nArmy in [1,
            # recruitable] and <= money / costPerSoldier — spend the coffer
            target = 200 + (money // 1200) * 50        # 67k coffer -> ~2.9k
            a["count"] = max(50, min(target, 9999) // 5 * 5)
        elif name == "send_gift":
            a["gold"] = _scale(int(money * 0.05), 200, 1500)
        elif name in ("buy_war", "coalition_war", "support_rebels"):
            a["gold"] = _scale(int(money * 0.10), 500, 5000)
    return actions
