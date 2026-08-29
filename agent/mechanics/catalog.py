"""L2 mechanics catalog — schema + validators (US1 skeleton; entries filled T027).

PRINCIPLE (spec FR-017③ 2026-08-29): operations (L1) != mechanics (L2).
A mechanic is a multi-turn behavioural sequence with trigger conditions;
prompt references must land on a VERIFIED entry (constitution VII).
"""
from __future__ import annotations

import re
from typing import Any

VERIFIED_SOURCE = "source"
VERIFIED_SMOKE = "smoke"

#: mid -> {id, verified: ["source"|"smoke"], trigger, phases:[{phase, ops, budget}], exit}
MECHANICS: dict[str, dict[str, Any]] = {}


def entry(mid: str) -> dict[str, Any] | None:
    return MECHANICS.get(mid)


def is_verified(mid: str) -> bool:
    e = MECHANICS.get(mid)
    return bool(e and (e.get("verified") or e.get("verified") == []) is not False
                and isinstance(e.get("verified"), list) and len(e["verified"]) > 0)


def verified_ids() -> set[str]:
    return {m for m in MECHANICS if is_verified(m)}


def assert_verified(mid: str) -> None:
    if not is_verified(mid):
        raise ValueError(f"mechanic not verified (no [source]/[smoke] mark): {mid}")


def refs_in(text: str) -> list[str]:
    """Mechanic ids that appear in a prompt/plan text."""
    found = []
    for mid in MECHANICS:
        if re.search(r"\b" + re.escape(mid) + r"\b", text or ""):
            found.append(mid)
    return found


def invalid_refs_in(text: str) -> list[str]:
    """Referenced-but-unverified mechanics (SC-009 / core guard for tests)."""
    return [m for m in refs_in(text) if not is_verified(m)]
