"""Message classification unit tests (three-kind model, user principle 2026-08-29)."""
import tempfile
from pathlib import Path

from agent.context_store import CtxStore
from agent.messages import (classify, decision_types, fixed_types, ignore_types,
                            resolve_params, FIXED_RULES, split_types)


def test_split_types():
    assert split_types("Message_War, Message_TechPoints") == ["Message_War", "Message_TechPoints"]
    assert split_types("") == []


def test_decision_class_table():
    for t in ("Message_War", "Message_PeaceTreaty", "Message_TradeReuest",
              "Message_Ultimatum", "Message_WeCanSignPeace", "Message_WeCanSignPeace_StatusQou",
              "Message_OfferVasalization", "Message_CallToArms", "Message_Independence_Ask",
              "Message_TransferControl", "Message_Union", "Message_PrepareForWar"):
        assert classify(t) == "decision", t


def test_fixed_uncivilized_rules_self_civilize():
    # 开化确认（游牧→君主制）：简单判断+数据变化 -> 固定流程（civilize 自己）
    assert classify("Message_Uncivilized") == "fixed"
    rule = FIXED_RULES["Message_Uncivilized"]
    assert rule["action"] == "civilize"
    assert resolve_params(rule["params"], {"my_civ": 205}) == {"target_civ_id": 205}
    assert fixed_types("Message_Uncivilized") == ["Message_Uncivilized"]
    assert "Message_Uncivilized" not in ignore_types("Message_Uncivilized")


def test_ignore_class_table():
    for t in ("Message_Relations_Increase", "Message_Relations_Increase_Ended",
              "Message_TechPoints", "Message_InvestDone",
              "Message_AssimilationEnd", "Message_Truce_Expired", "Message_Disease",
              "Message_PeaceTreaty_Accepted", "Message_NonAggressionPact_Denied",
              "Message_Bulit_Farm", "Message_HighInflation",
              # simple-judgement kinds whose bridge accept/decline actions are pending batch A
              "Message_NonAggressionPact", "Message_DefensivePact",
              "Message_MilitaryAccess_Ask", "Message_Gift"):
        assert classify(t) == "ignore", t


def test_decision_extract():
    raw = "Message_WeCanSignPeace,Message_Relations_Increase,Message_TechPoints"
    assert decision_types(raw) == ["Message_WeCanSignPeace"]
    assert ignore_types(raw) == ["Message_Relations_Increase", "Message_TechPoints"]


def test_context_record_roundtrip():
    store = CtxStore(Path(tempfile.mkdtemp()) / "ctx.json")
    store.add_event("decision", "Message_PeaceTreaty")
    store.add_event("fixed", "Message_Uncivilized:OK|civilize|205")
    reloaded = CtxStore(store.path)
    assert "Message_PeaceTreaty" in reloaded.decision_summary()
    kinds = [e["kind"] for e in reloaded.events]
    assert "fixed" in kinds and "decision" in kinds
