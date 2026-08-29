"""Unit tests for agent/state.py context assembly (no engine calls)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.state import (build_history, format_state_line, extract_ledger, ledger_line, threat_scan, RISK_RATIO)


def _sample_state():
    return {
        "turn": 7, "date": "1456", "money": 1250, "provinces": 4, "units": 600,
        "move_points": 5, "my_tech": 0.45, "capital": 241, "tech_points": 40,
        "messages": 2, "skills": {"eco_growth": 12, "research": 30},
        "province_detail": [{"id": 241, "pop": 1500, "dev": 40, "econ": 60,
                             "army": 100, "fort": 0, "capital": True}],
        "stability": {"hap_avg": 0.7, "rev_max": 0.1, "core": 4, "no_core": 0},
        "treaties": {"55": "truce"},
        "wars": [{"agg": 4, "def": 55}],
        "front_lines": [{"from": 241, "to": 300, "civ": 55,
                         "my_units": 100, "enemy_units": 80}],
        "neighbors": [{"civ_id": 55, "provinces": 8, "units": 300, "population": 90000,
                       "money": 500, "tech": 0.3, "relation": -35, "capital": 300,
                       "border_provinces": 3, "allied": False, "war": True}],
        "my_provinces": [241, 242],
    }


def test_format_state_line_covers_all_sections():
    line = format_state_line(_sample_state())
    for token in ("T7", "金1250", "省4", "军600", "科技点剩40", "技能:", "经济12",
                  "我方省份:", "稳定:", "条约:", "战争:", "前线:", "邻国:", "civ55"):
        assert token in line, f"missing: {token}"


def test_format_state_line_marks_war_and_alliance():
    st = _sample_state()
    st["neighbors"][0].update({"war": False, "allied": True})
    line = format_state_line(st)
    assert "(同盟)" in line
    assert "(交战!)" not in line


def test_build_history_no_file():
    assert build_history(Path("__no_such_dir__", "x"), limit=0) == "（无历史）"


def test_build_history_lines_append_only(tmp_path):
    lines = [
        {"turn": 1, "brief": "开局", "decision": [{"action": "invest", "province_id": 1, "gold": 100}]},
        {"turn": 2, "brief": "征兵", "decision": [{"action": "recruit_army", "province_id": 2, "count": 10}]},
    ]
    for ln in lines:
        (tmp_path / "turns.jsonl").open("a", encoding="utf-8").write(
            json.dumps(ln, ensure_ascii=False) + "\n")
    hist = build_history(tmp_path)
    assert hist.startswith("T1 开局 | 投province_id=1,gold=100")
    assert "T2 征兵 | 征province_id=2,count=10" in hist


def test_turn_context_contains_state_and_history():
    from agent.state import build_turn_context
    ctx = build_turn_context(_sample_state(), "T1 开局")
    assert "邻国:" in ctx and "T1 开局" in ctx and "我方省ID: 241,242" in ctx


def test_format_state_line_optional_fields_should():
    st = _sample_state()
    st["diplomacy_points"] = 18
    st["income"] = {"gold": 120, "move": 40, "diplo": 3, "tech": 0}
    st["low_stability_list"] = [241]
    st["war_score_res"] = {"mine": 0.62, "theirs": 0.31}
    st["neighbors"][0].update({"diplomacy_points": 5, "stability": 0.7,
                               "war_score": 0.31, "assimilates": [{"province_id": 300}]})
    line = format_state_line(st)
    assert "外点5" in line and "稳0.7" in line and "同化1" in line and "战争分0.31" in line
    assert "低稳省x1" in line
    assert "我0.62" in line and "敌0.31" in line


def test_format_state_line_optional_fields_absent_are_placeholders():
    line = format_state_line(_sample_state())
    assert "外点?" in line and "稳?" in line and "同化0" in line
    assert "低稳省x0" in line


def test_extract_ledger_includes_diplo_and_income():
    st = _sample_state()
    st["diplomacy_points"] = 22
    st["income"] = {"gold": 90, "move": 40, "diplo": 4, "tech": 3}
    lg = extract_ledger(st)
    assert lg["diplo_pts"] == 22
    assert lg["income"] == {"gold": 90, "move": 40, "diplo": 4, "tech": 3}
    l = ledger_line(lg)
    assert "外交点22" in l and "收金90" in l and "外4" in l


def test_extract_ledger_bridge_income_shape():
    # gateway /state income contract shape (EngineState.java): gold_in/gold_out/balance/diplo_delta
    st = _sample_state()
    st["income"] = {"gold_in": 150, "gold_out": 60, "balance": 90, "diplo_delta": 3}
    lg = extract_ledger(st)
    assert lg["income"]["gold"] == 90       # net = gold_in - gold_out
    assert lg["income"]["diplo"] == 3       # diplo_delta
    assert lg["income"]["move"] is None     # engine does not expose move income
    l = ledger_line(lg)
    assert "收金90" in l and "外3" in l and "点?" in l and "技?" in l


def test_ledger_line_placeholder_when_gold_missing():
    lg = {"gold": None, "move_pts": None, "diplo_pts": None, "tech_pts": None, "income": None}
    l = ledger_line(lg)
    assert "金?" in l and "行动点?" in l and "外交点?" in l and "科技点?" in l


def test_threat_scan_flags_hostile_overtake():
    st = _sample_state()
    st["units"] = 100
    st["neighbors"] = [{"civ_id": 55, "units": 500, "relation": -50, "war": False}]
    thr = threat_scan(st)
    assert thr and thr["civ_id"] == 55 and thr["ratio"] >= RISK_RATIO and not thr["war"]


def test_threat_scan_tiers_force_vs_hint():
    st = _sample_state()
    st["units"] = 100
    st["neighbors"] = [{"civ_id": 55, "units": 130, "relation": -60, "war": False}]  # 1.3x
    assert threat_scan(st, force_only=True) is None          # 打断级(1.5x)不触发
    soft = threat_scan(st, force_only=False)
    assert soft and soft["civ_id"] == 55                     # 提示级(1.2x)触发
    st["neighbors"][0]["units"] = 200                        # 2.0x -> force
    assert threat_scan(st, force_only=True)["civ_id"] == 55


def test_threat_scan_ignores_friendly_and_small():
    st = _sample_state()
    st["units"] = 100
    st["neighbors"] = [
        {"civ_id": 55, "units": 500, "relation": 30, "war": False},   # friendly big -> ignore
        {"civ_id": 56, "units": 90, "relation": -80, "war": False},   # small hostile -> ignore
    ]
    assert threat_scan(st) is None


def test_victory_progress_block_contents(tmp_path):
    from agent.state import victory_progress
    st = _sample_state()
    st["my_tech"] = 0.45
    st["units"] = 600
    st["neighbors"] = [{"civ_id": 55, "provinces": 8, "units": 300, "relation": -30,
                        "war": True, "population": 1, "money": 1, "tech": 1,
                        "capital": 1, "border_provinces": 1}]
    with (tmp_path / "turns.jsonl").open("w", encoding="utf-8") as f:
        for t in range(1, 6):
            f.write(json.dumps({"turn": t, "state": {"turn": t, "provinces": 3 + t,
                                                     "units": 100 * t}}) + "\n")
    line = victory_progress(st, tmp_path)
    for token in ("【胜利进展】", "科技", "领土", "邻国防务比", "趋势", "终局信号"):
        assert token in line, token
    assert "0.75×" in line or "civ55" in line
    assert "省净+2" in line or "净+" in line


def test_fill_empty_turns():
    from agent.main import _fill_empty_turns
    plan = {"turns": [{"offset": 1, "actions": [{"action": "invest", "province_id": 1, "gold": 500}]},
                      {"offset": 2, "actions": [], "note": "继续"},
                      {"offset": 3, "actions": []}]}
    _fill_empty_turns(plan, {"tech_points": 0, "my_provinces": [7]})
    assert plan["turns"][1]["actions"] == [{"action": "invest", "province_id": 1, "gold": 500}]
    assert plan["turns"][1]["note"].endswith("[fill]延续")
    # 延续链：后续空回合同样继承首动作（守卫征兵只在无前例时兜底）
    assert plan["turns"][2]["actions"] == [{"action": "invest", "province_id": 1, "gold": 500}]
    plan2 = {"turns": [{"offset": 1, "actions": []}]}
    _fill_empty_turns(plan2, {"tech_points": 12, "my_provinces": [7]})
    assert plan2["turns"][0]["actions"][0]["action"] == "invest_tech"
    # 首回合即空且无科技点 -> 守卫征兵（最后兜底）
    plan3 = {"turns": [{"offset": 1, "actions": [], "note": ""}, {"offset": 2, "actions": []}]}
    _fill_empty_turns(plan3, {"tech_points": 0, "my_provinces": [7]})
    assert plan3["turns"][0]["actions"][0]["action"] == "recruit_army"


def test_victory_progress_budget_sliders():
    from agent.state import victory_progress
    st = _sample_state()
    st["budget"] = {"taxation": 0.45, "goods": 0.3, "research": 0.15, "investments": 0.1}
    line = victory_progress(st, None)
    assert "预算(可调)" in line
    assert "税45%" in line and "研究15%" in line and "投资10%" in line


def test_threat_scan_war_flag_override():
    st = _sample_state()
    st["units"] = 100
    st["neighbors"] = [{"civ_id": 55, "units": 300, "relation": 5, "war": True}]
    thr = threat_scan(st)
    assert thr and thr["war"] is True
