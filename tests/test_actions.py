"""Unit tests for agent/actions.py parsing & validation (no engine calls)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from agent.actions import ActionError, parse_actions, parse_plan


def test_parse_actions_standard_list():
    raw = '{"actions":[{"action":"invest","province_id":1,"gold":100},' \
          '{"action":"recruit_army","province_id":2,"count":50}],"brief":"x"}'
    acts = parse_actions(raw)
    assert acts == [{"action": "invest", "province_id": 1, "gold": 100},
                    {"action": "recruit_army", "province_id": 2, "count": 50}]


def test_parse_actions_nested_single_key():
    raw = '[{"invest":{"province_id":1,"gold":100}}, {"peace_treaty":{"target_civ_id":9}}]'
    acts = parse_actions(raw)
    assert acts == [{"action": "invest", "province_id": 1, "gold": 100},
                    {"action": "peace_treaty", "target_civ_id": 9}]


def test_parse_actions_strips_code_fence():
    raw = '```json\n{"actions":[{"action":"invest","province_id":1,"gold":100}]}\n```'
    assert parse_actions(raw) == [{"action": "invest", "province_id": 1, "gold": 100}]


def test_parse_actions_unknown_action_raises():
    with pytest.raises(ActionError, match="unknown action"):
        parse_actions('[{"action":"nuke_moon","target_civ_id":1}]')


def test_parse_actions_bridge_only_commands_not_in_spec():
    # endTurn/respondMessages are bridge commands, not LLM actions
    with pytest.raises(ActionError, match="unknown action"):
        parse_actions('[{"action":"endTurn"}]')


def test_parse_actions_bad_param_type_raises():
    with pytest.raises(ActionError, match="param gold"):
        parse_actions('[{"action":"invest","province_id":1,"gold":"many"}]')


def test_parse_actions_invalid_tech_category():
    with pytest.raises(ActionError, match="invalid tech category"):
        parse_actions('[{"action":"invest_tech","category":"space","count":5}]')


def test_parse_actions_invalid_building_type():
    with pytest.raises(ActionError, match="invalid building type"):
        parse_actions('[{"action":"construct","building_type":"nuclear","province_id":1}]')


def test_parse_actions_not_json_raises():
    with pytest.raises((ActionError, ValueError)):
        parse_actions("我今天想先征兵再投资")


def test_parse_plan_offsets_and_cap():
    turns = [{"offset": 1, "actions": [{"action": "invest", "province_id": 1, "gold": 50}],
              "note": "a" * 100} for _ in range(12)]
    plan = parse_plan(json.dumps({"brief": "b", "turns": turns}))
    assert len(plan["turns"]) == 10  # capped at max_turns
    assert plan["turns"][0]["offset"] == 1
    assert len(plan["turns"][0]["note"]) <= 60
    assert plan["brief"] == "b"


def test_parse_plan_empty_raises():
    with pytest.raises(ActionError, match="empty plan"):
        parse_plan('{"turns":[]}')


def test_parse_plan_default_offsets():
    plan = parse_plan('[{"actions":[{"action":"invest","province_id":1,"gold":50}]}]')
    assert plan["turns"][0]["offset"] == 1
