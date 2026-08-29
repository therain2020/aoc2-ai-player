"""Unit tests for agent/state.py context assembly (no engine calls)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.state import build_history, format_state_line


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
