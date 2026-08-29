"""Resident context + persistent store for auto message handling.

- relations: civ_id -> {rel, war, allied, ts} refreshed from /state neighbors
  (authoritative snapshot) — surfaced into the next decision context for
  neighbor civs; non-neighbor civs stay in the store only.
- events: last N note entries (auto types / decision types pending) — surfaced
  into the next decision context as a summary line.

Persisted as JSON beside the game (game root / aoc2_context.json) so it
survives game restarts (constitution IV-style recovery).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

MAX_EVENTS = 24


class CtxStore:
    def __init__(self, path: Path):
        self.path = path
        self.relations: dict[str, dict] = {}
        self.events: list[dict] = []
        self.load()

    def load(self) -> None:
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.relations = data.get("relations", {})
                self.events = data.get("events", [])[-MAX_EVENTS:]
        except Exception:
            pass

    def save(self) -> None:
        try:
            self.path.write_text(
                json.dumps({"relations": self.relations, "events": self.events},
                           ensure_ascii=False),
                encoding="utf-8")
        except OSError:
            pass

    def sync_neighbors(self, neighbors: list[dict]) -> None:
        """Authoritative relation refresh from the /state neighbor snapshot."""
        for n in (neighbors or []):
            cid = n.get("civ_id")
            if cid is None:
                continue
            self.relations[str(cid)] = {
                "rel": n.get("relation"),
                "war": bool(n.get("war")),
                "allied": bool(n.get("allied")),
                "ts": int(time.time()),
            }
        self.save()

    def add_event(self, kind: str, detail: str) -> None:
        self.events.append({"kind": kind, "detail": detail, "ts": int(time.time())})
        self.events = self.events[-MAX_EVENTS:]
        self.save()

    def relation_line(self, neighbor_ids: set[str]) -> str:
        """Surfaced into LLM context: relation values for NEIGHBORS only."""
        parts = []
        for cid in sorted(self.relations):
            if cid not in {str(i) for i in neighbor_ids}:
                continue
            r = self.relations[cid]
            mark = ("交战" if r.get("war") else "同盟" if r.get("allied") else "")
            parts.append(f"civ{cid} 关系{r.get('rel','?')}{mark}")
        return "【常驻关系】" + " ".join(parts) if parts else ""

    def decision_summary(self, limit: int = 3) -> str:
        pending = [e for e in self.events if e.get("kind") == "decision"][-limit:]
        if not pending:
            return ""
        return "【待处决策消息】" + " / ".join(e["detail"] for e in pending)
