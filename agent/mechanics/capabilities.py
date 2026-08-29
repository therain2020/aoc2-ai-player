"""Capability layer (harness) — intent-level actions mapped to engine API sequences.

2026-08-29 user principle: simple prompt engineering is NOT enough for mechanics
like loans / buffer-vassal release / instigating wars — the agent decides the
INTENT, the harness executes it: preconditions (from /state) -> ordered engine
calls -> receipt verification -> fallback if a step fails.

Capability schema:
    name           intent identifier (LLM emits this, not raw engine APIs)
    decide         (st, ctx) -> plan | None   (intent-level reasoning/params)
    preconditions  (st) -> (ok, reason)       gate before any engine call
    steps          [(action, params_builder)] engine-call sequence (ACTION_SPEC)
    fallback       reason string used for ctx record if steps fail
    cost_tag       budget class for the sequence (FR-017①)
"""
from __future__ import annotations

from typing import Any, Callable

CAPABILITIES: dict[str, dict[str, Any]] = {}


def define(name: str, **fields) -> None:
    CAPABILITIES[name] = {
        "name": name,
        "preconditions": fields.get("preconditions", lambda st: (True, "")),
        "steps": fields.get("steps", []),
        "fallback": fields.get("fallback", f"{name} step failed"),
        "decide": fields.get("decide", lambda st, ctx: None),
    }


# ---- capability definitions (engine-verified Anchors in docs/mechanics.md) ----

define(
    "LOAN",
    preconditions=lambda st: (
        int(st.get("loans_size") or 0) < 5, "loan limit 5 reached"),
    steps=[("loan", {"gold": "ctx_gold", "duration": 12})],
    fallback="loan refused (limit/cost)",
    decide=lambda st, ctx: {"gold": 1000, "duration": 12} if (int(st.get("money") or 0) < 800) else None,
)

define(
    "REPAY_LOAN",
    preconditions=lambda st: (int(st.get("money") or 0) > 3000, "rich enough to repay"),
    steps=[("repay_loan", {"loan_id": "ctx_loan_id"})],
    fallback="repay refused",
    decide=lambda st, ctx: {"loan_id": 0} if (int(st.get("money") or 0) > 3000) else None,
)

define(
    "BUFFER_RELEASE",
    preconditions=lambda st: (
        bool(st.get("threat") and st.get("buffer_candidates")),
        "threatened and has releasable border province"),
    steps=[("release_buffer", {"tag": "ctx_tag", "provinces": "ctx_provinces"})],
    fallback="no releasable history tag for border province",
    decide=lambda st, ctx: ({"tag": ct.get("tag"), "provinces": ct.get("provinces")}
                            if (ct := ctx.get("buffer_candidate")) else None),
)

define(
    "INCITE_WAR",
    preconditions=lambda st: (
        int(st.get("money") or 0) >= 500 and bool(st.get("big_neighbor")),
        "coffer >= 500 and a big-neighbor target exists"),
    steps=[("buy_war", {"target_civ_id": "ctx_target",
                        "declare_war_on": "ctx_against", "gold": 500})],
    fallback="trade offer declined by AI",
    decide=lambda st, ctx: ({
        "target": tg, "against": ctx.get("big_neighbor", tg), "gold": 500}
        for tg in []),
)

define(
    "DOMINATE",
    preconditions=lambda st: (bool(st.get("weak_neighbor")), "a weaker neighbor exists"),
    steps=[("declare_war", {"target_civ_id": "ctx_target"}),
           ("move_army", {"front": "ctx_front"}),
           ("assimilate", {"province": "ctx_win"})],
    fallback="stalled / peace via war_cycle thresholds",
    decide=lambda st, ctx: ({"target": 0} if False else None),
)

define(
    "DEFEND_CORE",
    preconditions=lambda st: (bool(st.get("danger")), "under threat"),
    steps=[("construct", {"building_type": "fort", "province_id": "ctx_border"}),
           ("send_gift", {"target_civ_id": "ctx_aggressor", "gold": 200})],
    fallback="defensive fallout",
    decide=lambda st, ctx: ({} if False else None),
)


def capability_names() -> list[str]:
    return sorted(CAPABILITIES)


def get(name: str) -> dict[str, Any] | None:
    return CAPABILITIES.get(name)


def validate(plan: dict) -> bool:
    """Intent plan {intent, params} must reference a known capability."""
    return isinstance(plan, dict) and plan.get("intent") in CAPABILITIES
