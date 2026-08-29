"""War tactical commander tests (blitz orders, unlimited actions)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.mechanics.war_planner import plan_war_turn


def _st(fronts, move_pts=30, units=6000, provs=None):
    return {"front_lines": fronts, "move_points": move_pts, "units": units,
            "my_provinces": provs or [1, 2, 3],
            "neighbors": [{"civ_id": 55, "war": True, "capital": 900, "units": 1500}]}


def test_blitz_moves_all_attackable_full_regiment():
    st = _st([
        {"from": 10, "to": 100, "civ": 55, "my_units": 2000, "enemy_units": 300},
        {"from": 12, "to": 101, "civ": 55, "my_units": 4000, "enemy_units": 500},
        {"from": 13, "to": 102, "civ": 55, "my_units": 100, "enemy_units": 900},
    ])
    orders = plan_war_turn(st)
    moves = [o for o in orders if o["action"] == "move_army"]
    assert len(moves) == 2                       # 两条可攻前线全攻
    counts = {m["from_province"]: m["count"] for m in moves}
    assert counts[10] >= 1600                     # 2000×0.8 全压
    assert counts[12] >= 3200                     # 4000×0.8 全压
    recruits = [o for o in orders if o["action"] == "recruit_army"]
    assert 1 <= len(recruits) <= 2                # 动员最多 2 批（聚焦，不铺开）


def test_no_attack_then_mobilize_multiple():
    st = _st([{"from": 10, "to": 100, "civ": 55, "my_units": 5, "enemy_units": 200}], move_pts=30)
    orders = plan_war_turn(st)
    assert all(o["action"] == "recruit_army" for o in orders)
    assert len(orders) == 1                   # 1 个缺兵前方省 → 1 批（上限 2）
    assert orders[0]["province_id"] == 10     # 动员目标=缺兵前线省（部署正道）


def test_capital_priority():
    st = _st([
        {"from": 10, "to": 900, "civ": 55, "my_units": 500, "enemy_units": 120},   # 敌首都邻接
        {"from": 12, "to": 777, "civ": 55, "my_units": 2000, "enemy_units": 100},  # 兵力更多但非首都
    ])
    orders = plan_war_turn(st)
    moves = [o for o in orders if o["action"] == "move_army"]
    assert moves[0]["to_province"] == 900         # 优先奔袭敌首都


def test_guard_empty_front_and_never_empty_turn():
    # 战线我 0 兵 + 后方邻接省有兵 → 守备 move；且无空订单
    st = {"turn": 1, "units": 3000, "move_points": 40, "my_provinces": [10, 20],
          "my_civ": 4,
          "armies_overview": [{"prov": 10, "army": 0}, {"prov": 20, "army": 2000}],
          "adjacency": [{"mine": 20, "nbr": 10, "civ": 4}],
          "neighbors": [{"civ_id": 55, "war": True, "capital": 900, "units": 1500}],
          "front_lines": [{"from": 10, "to": 100, "civ": 55, "my_units": 0, "enemy_units": 300}]}
    orders = plan_war_turn(st)
    assert orders, "绝不空操作"
    guards = [o for o in orders if o["action"] == "move_army" and o["to_province"] == 10]
    assert guards and guards[0]["count"] >= 200   # 从 20 调兵守 10
