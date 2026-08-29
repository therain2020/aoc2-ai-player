"""Message classification unit tests (source-verified two-kind model)."""
import tempfile
from pathlib import Path

from agent.context_store import CtxStore
from agent.messages import classify, decision_types, auto_types, split_types


def test_split_types():
    assert split_types("Message_War, Message_TechPoints") == ["Message_War", "Message_TechPoints"]
    assert split_types("") == []


def test_decision_class_table():
    for t in ("Message_War", "Message_PeaceTreaty", "Message_TradeReuest",
              "Message_Ultimatum", "Message_WeCanSignPeace", "Message_WeCanSignPeace_StatusQou",
              "Message_NonAggressionPact", "Message_OfferVasalization",
              "Message_MilitaryAccess_Ask", "Message_CallToArms", "Message_Gift",
              "Message_Uncivilized"):   # 开化确认=体制转换决策（2026-08-29 用户指正）
        assert classify(t) == "decision", t


def test_auto_class_table():
    for t in ("Message_Relations_Increase", "Message_Relations_Increase_Ended",
              "Message_TechPoints", "Message_InvestDone",
              "Message_AssimilationEnd", "Message_Truce_Expired", "Message_Disease",
              "Message_PeaceTreaty_Accepted", "Message_NonAggressionPact_Denied",
              "Message_Bulit_Farm", "Message_HighInflation"):
        assert classify(t) == "auto", t


def test_decision_types_extract():
    raw = "Message_WeCanSignPeace,Message_Relations_Increase,Message_TechPoints"
    assert decision_types(raw) == ["Message_WeCanSignPeace"]
    assert auto_types(raw) == ["Message_Relations_Increase", "Message_TechPoints"]


def test_uncivilized_is_decision_and_no_auto():
    # 每回合重复推送由 MessageBox 去重；Agent 必须对开化确认做出回答（civilize 自己）
    assert classify("Message_Uncivilized") == "decision"
    assert "Message_Uncivilized" not in auto_types("Message_Uncivilized")
    assert decision_types("Message_Uncivilized") == ["Message_Uncivilized"]


def test_ctx_store_roundtrip(tmp_path: Path):
    store = CtxStore(tmp_path / "aoc2_context.json")
    store.sync_neighbors([{"civ_id": 5, "relation": -20, "war": False, "allied": False}])
    store.add_event("decision", "Message_PeaceTreaty")
    reloaded = CtxStore(tmp_path / "aoc2_context.json")
    assert reloaded.relations["5"]["rel"] == -20
    assert "Message_PeaceTreaty" in reloaded.decision_summary()


def test_ctx_relation_line_filters_non_neighbors():
    store = CtxStore(Path(tempfile.mkdtemp()) / "c.json")
    store.sync_neighbors([{"civ_id": 5, "relation": -20, "war": False, "allied": False},
                          {"civ_id": 88, "relation": 99, "war": False, "allied": False}])
    line = store.relation_line({5})
    assert "civ5" in line and "civ88" not in line
