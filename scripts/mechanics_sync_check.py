"""T048: docs/mechanics.md <-> agent/mechanics/catalog.py bidirectional consistency.

Direction A (docs -> catalog): every `### M-*` mechanic section must map to >=1
VERIFIED catalog entry whose doc_ref points into that section (M-TURN / AI-指纹
are documentation-only and allowed to have no entry).
Direction B (catalog -> docs): every catalog entry's doc_ref line must resolve to
a section whose M-code matches the entry's documented mapping.

Usage: python scripts/mechanics_sync_check.py   (exit 1 on any mismatch)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from agent.mechanics import catalog  # noqa: E402

DOC = REPO / "docs" / "mechanics.md"

# catalog id -> allowed M- codes (or literal section headings / doc-only)
MAPPING = {
    "war_cycle": ("M-WAR",),
    "internal_stability_gate": ("M-STABILITY",),
    "stability_revolt": ("M-STABILITY",),
    "assimilation_window": ("M-ASSIMILATE",),
    "diplo_economy": ("M-DIPLO-ECON",),
    "invest_cycle": ("M-ECON",),
    "tech_science": ("M-TECH",),
    "colonization": ("科技/殖民/查询",),
    "win_conditions": ("M-WIN",),
}

# M- sections that may exist without a catalog entry (documentation-only)
DOC_ONLY_SECTIONS = ("M-TURN",)


def sections(doc_text: str) -> list[tuple[str, int]]:
    out = []
    for i, line in enumerate(doc_text.splitlines(), start=1):
        m = re.match(r"^### (\S+)", line)
        if m:
            out.append((m.group(1), i))
    return out


def section_of(sections_list: list[tuple[str, int]], line_no: int) -> str | None:
    cur = None
    for heading, start in sections_list:
        if start <= line_no:
            cur = heading
        else:
            break
    return cur


def doc_ref_ranges(doc_ref: str) -> list[tuple[int, int]]:
    """'docs/mechanics.md:28-34,53-63,91-94' -> [(28,34),(53,63),(91,94)]."""
    out = []
    for part in str(doc_ref).split(","):
        m = re.search(r":?(\d+)(?:-(\d+))?", part)
        if m:
            out.append((int(m.group(1)), int(m.group(2) or m.group(1))))
    return out


def main() -> int:
    doc_text = DOC.read_text(encoding="utf-8")
    if not doc_text:
        print(f"[FATAL] {DOC} missing or empty")
        return 1
    secs = sections(doc_text)
    errors: list[str] = []

    # Direction A: every M-* section (except doc-only) has >=1 catalog entry
    # whose doc_ref (any range) points into it
    for heading, start in secs:
        if not heading.startswith("M-"):
            continue
        if heading in DOC_ONLY_SECTIONS:
            print(f"[ok] doc-only section {heading} (no catalog entry required)")
            continue
        mapped = [mid for mid, want in MAPPING.items() if heading in want]
        in_range = []
        for mid in mapped:
            e = catalog.entry(mid)
            if not e or not e.get("doc_ref"):
                continue
            for (s, _) in doc_ref_ranges(e["doc_ref"]):
                if section_of(secs, s) == heading:
                    in_range.append(mid)
        if not in_range:
            errors.append(f"A: section {heading} (L{start}) has no catalog entry pointing into it")

    # Direction B: every catalog entry's doc_ref must land (any range) in an allowed section
    for mid in sorted(catalog.MECHANICS):
        e = catalog.entry(mid)
        if not e or not e.get("doc_ref"):
            errors.append(f"B: {mid} missing doc_ref")
            continue
        if not catalog.is_verified(mid):
            errors.append(f"B: {mid} not verified")
            continue
        allowed = MAPPING.get(mid, ())
        if not allowed:
            errors.append(f"B: {mid} not in MAPPING (update the sync table)")
            continue
        hits = [section_of(secs, s) for (s, _) in doc_ref_ranges(e["doc_ref"])]
        if not any(h in allowed for h in hits):
            errors.append(f"B: {mid} doc_ref -> sections {hits} (allowed {allowed})")

    if errors:
        print(f"[FAIL] {len(errors)} inconsistency(ies)")
        for err in errors:
            print("  -", err)
        return 1
    print(f"[OK] mechanics catalog <-> docs/mechanics.md consistent "
          f"({len(catalog.MECHANICS)} entries, {len(secs)} sections)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
