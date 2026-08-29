"""Sanitizer tests (T3 disaster guard: illegal moves / multi-war burst)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.mechanics.sanitize import sanitize_actions


def _st():
    return {"front_lines": [{"from": 10, "to": 100, "civ": 55, "my_units": 2000, "enemy_units": 300}]}


def test_drops_non_front_moves():
    acts = [{"action": "move_army", "from_province": 523, "to_province": 1963, "count": 5},
            {"action": "move_army", "from_province": 10, "to_province": 100, "count": 5}]
    out = sanitize_actions(acts, _st())
    assert len(out) == 1 and out[0]["to_province"] == 100


def test_move_count_clamped_to_own_units_and_min10():
    out = sanitize_actions([{"action": "move_army", "from_province": 10, "to_province": 100,
                             "count": 3}], _st())
    assert out[0]["count"] == 10                    # min 10
    out2 = sanitize_actions([{"action": "move_army", "from_province": 10, "to_province": 100,
                              "count": 9999}], _st())
    assert out2[0]["count"] == 2000                 # ≤ province own units


def test_single_declare_war_per_turn():
    acts = [{"action": "declare_war", "target_civ_id": 134},
            {"action": "declare_war", "target_civ_id": 124}]
    out = sanitize_actions(acts, _st())
    assert len(out) == 1 and out[0]["target_civ_id"] == 134


def test_non_war_actions_pass_through():
    acts = [{"action": "recruit_army", "province_id": 1, "count": 100}]
    assert sanitize_actions(acts, _st()) == acts


def test_bankrupt_blocks_recruit():
    acts = [{"action": "recruit_army", "province_id": 1, "count": 100}]
    st = _st(); st["money"] = -500
    assert sanitize_actions(acts, st) == []


def test_recruit_capped_two_batches():
    acts = [{"action": "recruit_army", "province_id": i, "count": 400} for i in (1, 2, 3, 4)]
    assert len(sanitize_actions(acts, _st())) == 2
