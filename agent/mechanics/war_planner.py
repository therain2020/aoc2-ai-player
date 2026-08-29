"""War tactical commander — deterministic orders per war turn.

2026-08-29 user critique: war-by-LLM produces empty decisions & slow attacks;
blitz requires rule-based tempo. This planner emits concrete engine orders
every war turn (no LLM): target selection (enemy weakest flank / capital),
lightning concentration, mobilization. Stalemate auto-peace lives in main.
"""
from __future__ import annotations

MOVE_MIN = 10          # 单省进攻最小兵力（war_cycle 纪律）
COUNT_MULT = 4         # 进攻兵数 = 敌兵 × 4
MOBILIZE = 500


def plan_war_turn(st: dict) -> list[dict]:
    orders: list[dict] = []
    fronts = st.get("front_lines") or []
    provs = st.get("my_provinces") or [0]
    move_pts = int(st.get("move_points") or 0)

    # 敌首都 id（交战国邻的 capital）
    war_caps = {n.get("civ_id"): n.get("capital")
                for n in (st.get("neighbors") or []) if n.get("war")}

    # ① 可选进攻前线条目: 我≥10 且我>敌
    attackable = [f for f in fronts
                  if int(f.get("my_units") or 0) >= MOVE_MIN
                  and int(f.get("my_units") or 0) > int(f.get("enemy_units") or 0)]
    if attackable:
        # 目标优先级: 敌首都邻接 > 敌侧翼最弱
        t = None
        for f in attackable:
            if int(f.get("civ") or 0) in war_caps and int(f.get("to") or 0) == war_caps.get(f.get("civ")):
                t = f
                break
        if t is None:
            t = min(attackable, key=lambda f: int(f.get("enemy_units") or 9e9))
        my = int(t.get("my_units") or 0)
        # 调动=该省兵力全压（歼灭战；0.8 留驻防），绝不写死小数字（用户批评）
        count = max(int(my * 0.8), MOVE_MIN)
        orders.append({"action": "move_army", "from_province": int(t["from"]),
                       "to_province": int(t["to"]), "count": count})
        # 全线推进：全部可攻前线条目一回合全下（焦点=歼灭敌方存在，不设路数限制）
        others = [f for f in attackable if f is not t and int(f.get("my_units") or 0) >= MOVE_MIN
                  and int(f.get("my_units") or 0) > int(f.get("enemy_units") or 0)]
        for o in sorted(others, key=lambda f: int(f.get("enemy_units") or 9e9)):
            omy = int(o.get("my_units") or 0)
            orders.append({"action": "move_army", "from_province": int(o["from"]),
                           "to_province": int(o["to"]),
                           "count": max(int(omy * 0.8), MOVE_MIN)})

    # ③ 动员：批次由行动点动态决定（12 点/批），不设固定数量
    if move_pts >= 8:
        n_recruit = min(max(1, move_pts // 12), len(provs))
        for i in range(n_recruit):
            orders.append({"action": "recruit_army",
                           "province_id": int(provs[i]), "count": MOBILIZE})
    return orders


def weekly_strategy(st: dict) -> str:
    """War-strategy assessment for the periodic LLM call (stats only)."""
    my = int(st.get("units") or 0)
    parts = []
    for n in st.get("neighbors") or []:
        if n.get("war"):
            parts.append(f"敌civ{n.get('civ_id')} 省{n.get('provinces')} 军{n.get('units')} "
                         f"首都{n.get('capital')} 关系{n.get('relation')}（我{my}兵）")
    return "；".join(parts) or "无交战国"
