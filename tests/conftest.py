"""Shared fixtures: research asset paths (game root, decompiled source, game jar) and bridge port."""
import os
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]

GAME_ROOT = pathlib.Path(os.environ.get(
    "AOC2_GAME_ROOT",
    str(pathlib.Path.home() / "Downloads" / "Age of History II（含汉化）" / "Age of History II")))
ANALYSIS_ROOT = pathlib.Path(os.environ.get(
    "AOC2_ANALYSIS_ROOT",
    str(pathlib.Path.home() / "Downloads" / "_aoc2_analysis")))
AOC2_JAR = ANALYSIS_ROOT / "aoc2.jar"
DECOMPILED_ROOT = ANALYSIS_ROOT / "decompiled" / "age" / "of" / "civilizations2" / "jakowski" / "lukasz"
CFR_JAR = ANALYSIS_ROOT / "cfr-0.152.jar"

BRIDGE_PORT = 7187


def _require(path: pathlib.Path) -> str:
    assert path.exists(), f"missing research asset: {path}"
    return str(path)


@pytest.fixture(scope="session")
def aoc2_jar() -> str:
    return _require(AOC2_JAR)


@pytest.fixture(scope="session")
def decompiled_root() -> str:
    return _require(DECOMPILED_ROOT)


@pytest.fixture(scope="session")
def cfr_jar() -> str:
    return _require(CFR_JAR)
