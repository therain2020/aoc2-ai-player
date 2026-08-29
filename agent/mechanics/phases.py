"""Mechanic-phase recognition (data-model §5 ASSESS step, US1 minimal set).

Output: Phase(phase_id, tactic_ref, reasons) — tactic_ref is only ever set to
a VERIFIED catalog id (constitution VII); catalog is populated at T027, so the
US1 loop labels phases while tactics stay None until entries exist.
"""
from __future__ import annotations

from typing import NamedTuple

from agent.mechanics import catalog


class Phase(NamedTuple):
    phase_id: str
    tactic_ref: str | None
    reasons: list[str]


def _tactic(mid: str) -> str | None:
    return mid if catalog.entry(mid) is not None and catalog.is_verified(mid) else None


def assess(st: dict | None) -> Phase:
    if not isinstance(st, dict):
        return Phase("unknown", None, ["no state"])

    # terminal conditions first — the game is over, do not act
    if st.get("game_end") is True:
        return Phase("ended", None, ["game_end signal"])

    # start-screen preview guard (in_game=false && turn<=1 => not a game)
    if not st.get("in_game", False) and int(st.get("turn", 1) or 1) <= 1:
        return Phase("not_in_game", None, ["menu preview / not loaded"])

    wars = st.get("wars") or []
    neighbor_war = any(n.get("war") for n in st.get("neighbors", []))
    if wars or neighbor_war:
        return Phase("war_cycle", _tactic("war_cycle"), ["at_war"])

    stab = st.get("stability") or {}
    rev_max = stab.get("rev_max")
    low_stab = st.get("low_stability_list") or []
    if isinstance(rev_max, (int, float)) and rev_max > 0.16:
        return Phase("internal_stability_gate", _tactic("internal_stability_gate"),
                     [f"rev_risk={rev_max}"])
    if low_stab:
        return Phase("internal_stability_gate", _tactic("internal_stability_gate"),
                     [f"low_stability=x{len(low_stab)}"])

    return Phase("peace_economy", None, ["stable"])
