"""Unit tests for agent/actions.py parsing & validation (no engine calls)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from agent.actions import (ActionError, parse_actions, parse_plan, cost_of, untagged, COST_TAGS)


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


def test_parse_plan_tactic_ref_verified_kept():
    plan = parse_plan('{"turns":[{"tactic_ref":"war_cycle","actions":[]}]}')
    assert plan["turns"][0]["tactic_ref"] == "war_cycle"


def test_parse_plan_tactic_ref_unverified_raises():
    with pytest.raises(ActionError, match="unverified tactic_ref"):
        parse_plan('{"turns":[{"tactic_ref":"made_up_mech","actions":[]}]}')


def test_parse_plan_legacy_no_ref_bagged():
    plan = parse_plan('{"turns":[{"actions":[]},{"tactic_ref":"tech_science","actions":[]}]}')
    assert plan["no_ref"] == 1
    assert plan["turns"][1]["tactic_ref"] == "tech_science"


def test_cost_tags_zero_miss():
    assert untagged() == []


def test_cost_of_l1_diplo_actions():
    assert cost_of("ultimatum") == "diplo"
    assert cost_of("support_rebels") == "multi"
    assert cost_of("prepare_for_war") == "move"
    assert cost_of("send_gift") == COST_TAGS["send_gift"]


def test_parse_actions_new_l1_actions():
    acts = parse_actions('[{"action":"send_gift","target_civ_id":4,"gold":200},'
                         '{"action":"form_civilization"},'
                         '{"action":"prepare_for_war","target_civ_id":3,"against_civ_id":5}]')
    assert acts[0] == {"action": "send_gift", "target_civ_id": 4, "gold": 200}
    assert acts[1] == {"action": "form_civilization"}
    assert acts[2]["against_civ_id"] == 5


def test_result_ok_accepts_all_receipt_shapes():
    from agent.actions import result_ok
    # EngineGateway JSON text receipt
    assert result_ok('{"result":"OK","log":"OK|recruitArmy|1957|10","detail":{}}')
    assert not result_ok('{"result":"FAIL","log":"FAIL|invest|1958|100","detail":{}}')
    # legacy pipe receipt
    assert result_ok("OK|invest|1|2")
    assert not result_ok("FAIL|moveArmy|1|2|3")
    # dict receipt (in-test doubles)
    assert result_ok({"result": "OK"})
    assert not result_ok({"result": "FAIL"})
    assert not result_ok("not a receipt")
