"""Decision cadence (data-model §8; spec FR-008/SC-001 revision, 2026-08-29).

New paradigm: no per-10-turn action plans — the agent decides per turn when the
cadence says so. Cadence rule:
  - regular decision every CADENCE_TURNS (2) turns, or
  - immediately on key events: wars transition, territory loss,
    decision-class message, strategy change (external sig), vision expiry.
"""
from __future__ import annotations

CADENCE_TURNS = 2
VISION_SPAN = 10


def _wars_sig(wars) -> str:
    if not isinstance(wars, list):
        return ""
    return ";".join(f"{w.get('agg')}>{w.get('def')}" for w in wars if isinstance(w, dict))


class CadenceTracker:
    """Stateful cadence judge: remembers last war/territory/msg/strategy state."""

    def __init__(self, cadence: int = CADENCE_TURNS, vision_span: int = VISION_SPAN):
        self.cadence = cadence
        self.vision_span = vision_span
        self.last_decision_turn = -999
        self.last_wars = None            # None = uninitialized (first sight baseline)
        self.last_provinces = None
        self.last_decision_msg = ""      # decision-class message signature only
        self.last_strategy_sig = None
        self.vision_turn = None          # turn when the current vision was generated

    def mark_decision(self, cur: int, st: dict) -> None:
        self.last_decision_turn = cur
        self.last_wars = _wars_sig(st.get("wars"))
        self.last_provinces = int(st.get("provinces") or 0)

    def mark_decision_msg(self, sig: str) -> None:
        self.last_decision_msg = sig or ""

    def set_vision(self, cur: int) -> None:
        self.vision_turn = cur

    def should_decide(self, cur: int, st: dict,
                      decision_msg_sig: str | None = None,
                      strategy_changed: bool = False) -> tuple[bool, str]:
        """(decide?, reason). Caller feeds decision_msg_sig only when a
        decision-class message arrived; strategy_changed when strategy sig
        differs from the last seen (R006 wires both)."""
        wars = _wars_sig(st.get("wars"))
        if self.last_wars is not None and wars != self.last_wars:
            return True, "wars 转变"
        provinces = int(st.get("provinces") or 0)
        if self.last_provinces is not None and provinces < self.last_provinces:
            return True, "领土损失"
        if decision_msg_sig is not None and decision_msg_sig != self.last_decision_msg:
            return True, "决策消息"
        if strategy_changed:
            return True, "战略变化"
        if self.vision_turn is not None and cur - self.vision_turn >= self.vision_span:
            return True, "愿景到期"
        if cur - self.last_decision_turn >= self.cadence:
            return True, "节拍"
        return False, ""
