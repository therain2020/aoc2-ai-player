"""Intent -> capability injector tests (harness intent-decomposer)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.mechanics import intent_writer as iw


def _st(**kw):
    st = {
        "money": 5000, "diplomacy_points": 40, "units": 1000,
        "my_provinces": [1, 2, 3],
        "front_lines": [{"from": 2, "to": 9, "civ": 89, "my_units": 100, "enemy_units": 90}],
        "neighbors": [
            {"civ_id": 89, "provinces": 200, "units": 3000, "relation": -50, "border_provinces": [2]},
            {"civ_id": 90, "provinces": 300, "units": 3500, "relation": 20, "border_provinces": [3]},
            {"civ_id": 91, "provinces": 10, "units": 200, "relation": -20, "border_provinces": []},
        ],
    }
    st.update(kw)
    return st


def test_detect_intents_keywords():
    assert "INCITE_WAR" in iw.detect_intents("挑拨强邻互斗")
    assert "ALLEGIANCE_CHAIN" in iw.detect_intents("联合统治合并提议")
    assert "BUDGET_TUNE" in iw.detect_intents("调整预算税收")
    assert iw.detect_intents("继续征兵投资") == []


def test_resolve_params_civ_from_text():
    p = iw.resolve_params("INCITE_WAR", _st(), "对civ135与civ136挑拨")
    assert p["target"] == 135 and p["against"] == 136


def test_resolve_params_picks_big_and_second():
    p = iw.resolve_params("INCITE_WAR", _st(), "")
    assert p["target"] == 90      # 最大省(300)
    assert p["against"] == 89     # 次大(200)


def test_inject_budget_gates_and_dedup():
    st = _st(money=300)                       # <500 -> incite 注入失败（预算门）
    plan = {"turns": [{"offset": 1, "actions": []} for _ in range(5)]}
    notes = iw.inject(plan, ["INCITE_WAR"], st, "")
    assert notes == []
    st2 = _st(money=5000)
    notes2 = iw.inject(plan, ["ALLEGIANCE_CHAIN"], st2, "")
    acts = [a["action"] for t in plan["turns"] for a in t.get("actions", [])]
    assert "guarantee_independence" in acts and "union_proposal" in acts and "offer_alliance" in acts
    # 不重复注入
    notes3 = iw.inject(plan, ["ALLEGIANCE_CHAIN"], st2, "")
    assert notes3 == []


def test_strategy_mandate_war_command():
    st = {"units": 1000,
          "neighbors": [{"civ_id": 90, "units": 400, "provinces": 5, "war": False, "allied": False},
                        {"civ_id": 91, "units": 5000, "war": False, "allied": False}]}
    m = iw.strategy_mandate("挑选一个弱小的邻国宣战", st)
    assert m == [{"action": "declare_war", "target_civ_id": 90}]
    assert iw.strategy_mandate("全力发展内政", st) == []
    st2 = {"units": 1000, "neighbors": [{"civ_id": 91, "units": 5000, "war": False, "allied": False}]}
    assert iw.strategy_mandate("宣战弱邻", st2) == []      # 无弱候选

def test_enrich_preempt_when_weak_stabilizes():
    st = _st()   # civ89 3000 = 3x mine(1000) -> danger
    plan = {"turns": [{"offset": 1, "actions": []}, {"offset": 2, "actions": []}]}
    notes = iw.enrich(plan, "威胁巨大，先发制人", st, {"civ_id": 89, "units": 3000, "ratio": 3.0})
    acts = [a["action"] for t in plan["turns"] for a in t.get("actions", [])]
    assert "declare_war" not in acts               # 劣势不禁宣战
    assert "send_gift" in acts and "improve_relations" in acts
    assert "danger_stabilize:send_gift" in notes


def test_enrich_preempt_when_strong_declares():
    st = _st(units=5000)                          # civ89 3000 vs 5000 = 占优
    plan = {"turns": [{"offset": 1, "actions": []} for _ in range(2)]}
    notes = iw.enrich(plan, "先发制人宣战", st, {"civ_id": 89, "units": 3000, "ratio": 0.6})
    acts = [a["action"] for t in plan["turns"] for a in t.get("actions", [])]
    assert "declare_war" in acts
    assert "danger_preempt:declare_war" in notes
