"""R002/R003 tests: vision generator + reserve discipline (FR-017⑤/SC-011)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.mechanics import reserve, vision


class FakeProvider:
    def chat(self, system, user, temperature=0.7, max_tokens=700):
        return '{"brief": "先灭 civ128，扩张至60省，科技领先。", "focus": ["军备", "扩张"]}'


def test_generate_vision_shape(tmp_path):
    v = vision.generate_vision(FakeProvider(),
                               {"turn": 5, "money": 3000, "move_points": 40,
                                "diplomacy_points": 20, "tech_points": 10,
                                "income": {"gold": 100}, "units": 500, "provinces": 41,
                                "my_provinces": [1], "neighbors": [],
                                "game_end": {"ended": False}},
                               tmp_path)
    assert v["kind"] == "vision" and v["brief"]
    assert len(v["brief"]) <= 120 and len(v["focus"]) <= 3
    assert v["base_turn"] == 5


def test_vision_persistence_and_expiry(tmp_path):
    v = {"kind": "vision", "brief": "x", "base_turn": 1, "generated_turn": 1}
    vision.write_vision(tmp_path, v)
    got = vision.read_vision(tmp_path)
    assert got["kind"] == "vision"
    assert vision.vision_expired(got, 10) is False
    assert vision.vision_expired(got, 11) is True


def test_gold_floor_dynamic():
    st = {"income": {"gold": 120}}
    assert reserve.gold_floor(st) == 360.0                # 3× 净收入
    st2 = {"income": {"gold": -5}}
    assert reserve.gold_floor(st2) == 0.0                 # 负收入 -> 无正向下限
    st3 = {"income": {}}
    assert reserve.gold_floor(st3, [80, 100, 120]) == 300.0  # trailing mean ×3


def test_reserve_guard_breach():
    guard = reserve.reserve_guard({"money": 200}, 360.0)
    assert guard["breached"] is True and "修复收入" in guard["note"]
    ok = reserve.reserve_guard({"money": 2000}, 360.0)
    assert ok["breached"] is False


def test_reserve_line_concise():
    line = reserve.reserve_line({"money": 5000, "income": {"gold": 120}})
    assert "储备线" in line and "✓" in line
    bad = reserve.reserve_line({"money": 50, "income": {"gold": 120}})
    assert "修复收入" in bad
