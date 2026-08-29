"""Catalog + prompt consistency guards (SC-009: prompts only reference verified mechanics)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.mechanics import catalog, prompts


def test_catalog_entries_all_verified():
    ids = sorted(catalog.MECHANICS)
    assert ids == sorted(catalog.verified_ids())
    assert len(ids) == 9
    for mid, e in catalog.MECHANICS.items():
        assert e["id"] == mid
        assert set(("id", "verified", "trigger", "phases", "exit", "doc_ref")) <= set(e)


def test_catalog_entry_schema_phases():
    for e in catalog.MECHANICS.values():
        assert e["phases"], e["id"]
        for p in e["phases"]:
            assert p["phase"] and p["ops"] and p["budget"], e["id"]
        assert e["doc_ref"].startswith("docs/mechanics.md:"), e["id"]


def test_catalog_invalid_refs_detection():
    assert catalog.invalid_refs_in("use war_cycle now") == []
    assert catalog.invalid_refs_in("fight phony_mechanics_war") == []


def test_prompts_reference_only_verified():
    plan = prompts.build_plan_system()
    war = prompts.build_war_system()
    assert catalog.invalid_refs_in(plan) == []
    assert catalog.invalid_refs_in(war) == []
    guidance = prompts.mechanic_guidance()
    for mid in catalog.verified_ids():
        assert mid in guidance


def test_mechanic_guidance_no_unimplemented_ops_in_action_spec():
    # every op mentioned in guidance must be either implemented or explicitly marked pending
    from agent.actions import ACTION_SPEC
    g = prompts.mechanic_guidance("assimilation_window")
    assert "assimilate" in g


def test_plan_spec_has_budget_and_principles():
    spec = prompts.plan_batch_spec()
    assert "资源台账" in spec and "成本四原则" in spec and "tactic_ref" in spec
    assert "封顶" in spec


def test_budget_guard_low_gold_blocks_gold_actions():
    guard = prompts.budget_guard({"gold": -90, "income": {"gold": -3, "diplo": 8}})
    assert "预算护栏" in guard and "禁止一切金币动作" in guard
    assert "invest" in guard
    g_rich = prompts.budget_guard({"gold": 5000, "income": {"gold": 120, "diplo": 3}})
    assert g_rich == ""
    g_edge = prompts.budget_guard({"gold": 500, "income": {}})
    assert g_edge == ""  # 500 == GOLD_SAFE 不算低