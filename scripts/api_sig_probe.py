"""Batch javap signature probe -> tests/expected_signatures.json (anti-drift baseline).

The bridge must only call engine methods whose signatures are pinned here; the JSON is
consumed by tests (Phase D) and by docs/mechanics.md sync tooling.

Usage:
    python scripts/api_sig_probe.py                                   # default class set
    python scripts/api_sig_probe.py --classes DiplomacyManager,War_GameData
    python scripts/api_sig_probe.py --classes-from <file>             # one class per line
    python scripts/api_sig_probe.py --out <json> --jar <aoc2.jar>
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_JAR = pathlib.Path.home() / "Downloads" / "_aoc2_analysis" / "aoc2.jar"
DEFAULT_OUT = REPO / "tests" / "expected_signatures.json"
PACKAGE = "age.of.civilizations2.jakowski.lukasz"
DEFAULT_CLASSES = (
    "DiplomacyManager",
    "PeaceTreaty_GameData",
    "PeaceTreaty_Data",
    "War_GameData",
    "Game",
    "Game_Action",
    "Game_NextTurnUpdate",
    "Civilization",
    "CivGameData",
    "VicotryManager",
    "Game_Calendar",
    "BuildingsManager",
    "SkillsManager",
)


def probe(jar: pathlib.Path, classes: list[str]) -> dict[str, list[str]]:
    javap = shutil.which("javap")
    if not javap:
        sys.exit("[ERROR] javap not found (need JDK on PATH)")
    out: dict[str, list[str]] = {}
    for name in classes:
        full = name if "." in name else f"{PACKAGE}.{name}"
        r = subprocess.run(
            [javap, "-p", "-classpath", str(jar), full],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        out[full] = [] if r.returncode != 0 else [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
        if r.returncode != 0:
            print(f"[WARN] javap failed: {full}: {r.stderr.strip()[:120]}", file=sys.stderr)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jar", type=pathlib.Path, default=DEFAULT_JAR)
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    ap.add_argument("--classes")
    ap.add_argument("--classes-from", type=pathlib.Path)
    args = ap.parse_args()

    classes: list[str]
    if args.classes_from:
        classes = [ln.strip() for ln in args.classes_from.read_text(encoding="utf-8").splitlines() if ln.strip()]
    elif args.classes:
        classes = [c.strip() for c in args.classes.split(",") if c.strip()]
    else:
        classes = list(DEFAULT_CLASSES)

    if not args.jar.exists():
        sys.exit(f"[ERROR] jar missing: {args.jar}")
    sig = probe(args.jar, classes)
    args.out.write_text(json.dumps(sig, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[OK] {len(sig)} classes -> {args.out}")


if __name__ == "__main__":
    main()
