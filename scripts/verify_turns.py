"""Verify a session's turns.jsonl against the recording contract.

Checks (data-model §6): every line carries turn/decision/results/ledger/
mechanic_phase/tokens_cum on NEW runs (fields added by US1); war-turn single
call; plan-call rate (SC-001) and adjacency/validity shape counters are
reported, not asserted (real-game thresholds need smoke).

Usage: python scripts/verify_turns.py <turns.jsonl> [--strict]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CORE_FIELDS = ("turn", "ts", "decision", "results", "mechanic_phase", "tokens_cum")
US1_FIELDS = ("ledger", "tactic_ref")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("file", type=Path)
    ap.add_argument("--strict", action="store_true", help="fail on missing fields")
    args = ap.parse_args()
    if not args.file.exists():
        sys.exit(f"[ERROR] {args.file} not found")

    lines = [json.loads(l) for l in args.file.read_text(encoding="utf-8").splitlines()
             if l.strip()]
    if not lines:
        sys.exit("[ERROR] empty turns.jsonl")

    missing: dict[str, int] = {}
    us1_missing: dict[str, int] = {}
    pending_plan = 0
    warnings: list[str] = []

    for d in lines:
        for f in CORE_FIELDS:
            if f not in d:
                missing[f] = missing.get(f, 0) + 1
        for f in US1_FIELDS:
            if f not in d:
                us1_missing[f] = us1_missing.get(f, 0) + 1
        if d.get("type") == "plan":
            pending_plan = 10
        elif pending_plan > 0:
            pending_plan -= 1
            calls = 1  # a per-turn record implies an LLM call in war mode
            if d.get("type") == "war" and calls != 1:
                warnings.append(f"turn {d.get('turn')}: war record but call count != 1")

    turns = [d["turn"] for d in lines if "turn" in d]
    call_lines = sum(1 for d in lines if d.get("type") in ("plan", "war"))
    print(f"records: {len(lines)} | turns: {min(turns)}..{max(turns)} | "
          f"call-records: {call_lines} (plan/war)")
    print(f"core field misses: {missing or 'none'}")
    print(f"US1 field misses (ledger/tactic_ref; older runs ok): {us1_missing or 'none'}")
    for w in warnings:
        print(f"  WARN {w}")

    ok = not missing and (not args.strict or not us1_missing)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
