"""Refresh/regenerate the decompiled game source via CFR (local research asset, gitignored).

Defaults point at the established research dirs; output goes to
game_bridge/engine_gateway/analysis/ so the bridge sources stay near their ground truth.

Usage:
    python scripts/rebuild_analysis.py                      # full refresh (slow, ~min)
    python scripts/rebuild_analysis.py --class DiplomacyManager   # single class only (fast)
    python scripts/rebuild_analysis.py --jar <path> --out <dir> --cfr <path>
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
from pathlib import Path

REPO = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_CFR = pathlib.Path.home() / "Downloads" / "_aoc2_analysis" / "cfr-0.152.jar"
DEFAULT_JAR = pathlib.Path.home() / "Downloads" / "_aoc2_analysis" / "aoc2.jar"
DEFAULT_OUT = REPO / "game_bridge" / "engine_gateway" / "analysis"
PACKAGE = "age.of.civilizations2.jakowski.lukasz"
PUBLIC_CLASSES = (
    "EngineGatewayMeta",
    "DiplomacyManager",
    "PeaceTreaty_GameData",
    "PeaceTreaty_Data",
    "War_GameData",
    "Game_NextTurnUpdate",
    "Game_Action",
    "VicotryManager",
)


def refresh(cfr: Path, jar: Path, out: Path, cls: str | None = None) -> None:
    if not cfr.exists():
        sys.exit(f"[ERROR] CFR jar missing: {cfr} (set --cfr)")
    if not jar.exists():
        sys.exit(f"[ERROR] jar missing: {jar} (set --jar)")
    out.mkdir(parents=True, exist_ok=True)
    cmd = ["java", "-jar", str(cfr), str(jar), "--outputdir", str(out)]
    if cls:
        cmd.append(f"{PACKAGE}.{cls}")
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"[OK] decompiled -> {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jar", type=pathlib.Path, default=DEFAULT_JAR)
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    ap.add_argument("--cfr", type=pathlib.Path, default=DEFAULT_CFR)
    ap.add_argument("--class", dest="cls", choices=PUBLIC_CLASSES)
    args = ap.parse_args()
    refresh(args.cfr, args.jar, args.out, args.cls)


if __name__ == "__main__":
    main()
