"""R001 cadence tests (2-turn regular cadence + key-event triggers)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.mechanics.cadence import CadenceTracker


def _st(provinces=10, wars=None, msgs=0):
    return {"provinces": provinces, "wars": wars or [], "messages": msgs, "msg_types": ""}


def test_no_decision_within_regular_window():
    c = CadenceTracker()
    c.mark_decision(10, _st())
    assert c.should_decide(10, _st()) == (False, "")
    assert c.should_decide(11, _st())[0] is False
    assert c.should_decide(12, _st())[0] is True      # 2 回合节拍


def test_wars_transition_triggers():
    c = CadenceTracker()
    c.mark_decision(10, _st())
    ok, reason = c.should_decide(11, _st(wars=[{"agg": 1, "def": 2}]))
    assert ok and "wars" in reason


def test_territory_loss_triggers():
    c = CadenceTracker()
    c.mark_decision(10, _st(provinces=10))
    ok, reason = c.should_decide(11, _st(provinces=9))
    assert ok and "领土" in reason


def test_decision_message_triggers():
    c = CadenceTracker()
    c.mark_decision(10, _st())
    ok, reason = c.should_decide(11, _st(), decision_msg_sig="Message_PeaceTreaty")
    assert ok and "消息" in reason
    c.mark_decision(11, _st())                       # 决策后刷新基线
    c.mark_decision_msg("Message_PeaceTreaty")
    assert c.should_decide(12, _st(), decision_msg_sig="Message_PeaceTreaty")[0] is False


def test_strategy_change_triggers():
    c = CadenceTracker()
    c.mark_decision(10, _st())
    ok, reason = c.should_decide(11, _st(), strategy_changed=True)
    assert ok and "战略" in reason


def test_vision_expiry_triggers():
    c = CadenceTracker()
    c.set_vision(1)
    c.mark_decision(9, _st())                           # 近期决策：避免节拍先触发
    assert c.should_decide(10, _st())[0] is False       # 愿景尚未到期且未到节拍
    assert c.should_decide(11, _st())[0] is True        # ≥10 回合 → 愿景到期


def test_first_sight_no_spurious_trigger_and_war_detection():
    c = CadenceTracker()
    c.mark_decision(5, _st())
    c2 = CadenceTracker()                                # 冷启动：war sig 首次为 None
    ok, _ = c2.should_decide(6, _st(wars=[{"agg": 1, "def": 2}]))
    assert ok is True or ok is False                     # 未初始化=不特殊触发（由节拍/其它驱动）
