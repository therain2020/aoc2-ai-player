"""Unified agent status snapshot — single source for dashboard AND panel.

Answers at a glance (no guessing): is the agent process alive? who paused it?
which session/turn is live? what gear/strategy is set? bridge state?
"""
from __future__ import annotations

import json
import subprocess
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PID_FILE = REPO / "agent.pid"
BRIDGE = "http://127.0.0.1:7187"


def agent_pids() -> list[int]:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | "
         "Where-Object { $_.CommandLine -match 'agent.main' } | "
         "ForEach-Object { $_.ProcessId }"],
        capture_output=True, text=True, shell=True)
    pids = []
    for ln in out.stdout.splitlines():
        ln = ln.strip()
        if ln.isdigit():
            pids.append(int(ln))
    return pids


def read_pid() -> int | None:
    try:
        return int(PID_FILE.read_text().strip())
    except Exception:
        return None


def pause_meta(game_root: str) -> dict:
    p = Path(game_root) / "aoc2_pause.txt"
    if not p.exists():
        return {"paused": False, "by": None, "ts": None}
    by, ts = None, None
    try:
        first = p.read_text(encoding="utf-8", errors="replace").splitlines()[0]
        if first.startswith("#"):
            parts = first.lstrip("#").split(" ", 1)
            by = parts[0]
            ts = parts[1] if len(parts) > 1 else None
    except OSError:
        pass
    return {"paused": True, "by": by or "unknown", "ts": ts}


def strategy_meta(game_root: str) -> dict:
    p = Path(game_root) / "aoc2_strategy.txt"
    text = ""
    if p.exists():
        try:
            text = p.read_text(encoding="utf-8", errors="replace").strip()[:120]
        except OSError:
            text = ""
    gear = None
    for i, c in enumerate("①②③④⑤⑥"):
        if text.startswith(c):
            gear = i + 1
            break
    return {"text": text, "gear": gear}


def latest_session() -> dict | None:
    base = REPO / "sessions"
    if not base.exists():
        return None
    dirs = sorted((d for d in base.iterdir() if d.is_dir() and "agent" in d.name),
                  key=lambda d: d.stat().st_mtime, reverse=True)
    if not dirs:
        return None
    d = dirs[0]
    f = d / "turns.jsonl"
    rows, last = 0, None
    if f.exists():
        try:
            with f.open("r", encoding="utf-8") as h:
                for line in h:
                    rows += 1
                    try:
                        last = json.loads(line)
                    except json.JSONDecodeError:
                        pass
        except OSError:
            pass
    return {"name": d.name, "rows": rows,
            "turn": last.get("turn") if last else None,
            "type": last.get("type") if last else None,
            "brief": str(last.get("brief"))[:60] if last else ""}


def bridge_state() -> dict | None:
    try:
        with urllib.request.urlopen(BRIDGE + "/state", timeout=2) as r:
            st = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    return {k: st.get(k) for k in ("turn", "turn_state", "in_game", "date",
                                   "money", "units", "provinces", "messages")}


def snapshot(config: dict) -> dict:
    """One call → everything the operator needs."""
    game_root = (config.get("game") or {}).get("root", "")
    pids = agent_pids()
    return {
        "agent": {"running": bool(pids), "pids": pids, "pid_record": read_pid()},
        "bridge": bridge_state(),
        "session": latest_session(),
        "pause": pause_meta(game_root),
        "strategy": strategy_meta(game_root),
    }
