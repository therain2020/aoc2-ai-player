"""Vision generator (FR-008 revised, spec-kit R002).

Replaces action-level batch plans with a 10-turn textual vision:
  {"kind": "vision", "brief": "≤120 字方向", "focus": [...], "base_turn", "generated_turn"}
Persisted to plan.json (new schema); dashboard renders the brief only.
"""
from __future__ import annotations

import json
from pathlib import Path

VISION_SPAN = 10


def generate_vision(provider, st: dict, session_dir: Path, strat: str = "") -> dict:
    """Produce a vision dict via the LLM (JSON {brief, focus})."""
    from agent.mechanics import prompts as mech_prompts
    from agent.state import build_turn_context, ledger_line, victory_progress
    inc = st.get("income") or {}
    ledger = {
        "gold": st.get("money"),
        "move_pts": st.get("move_points"),
        "diplo_pts": st.get("diplomacy_points"),
        "tech_pts": st.get("tech_points"),
        "income": {k: inc.get(k) for k in ("gold", "move", "diplo", "tech")} if inc else None,
    }
    ctx = build_turn_context(st, "（无历史）")
    if strat:
        ctx = "【用户战略指示】" + str(strat) + "\n" + ctx
    ctx = ledger_line(ledger) + "\n" + victory_progress(st, session_dir) + "\n" + ctx
    raw = provider.chat(mech_prompts.build_vision_system(), ctx,
                        temperature=0.3, max_tokens=800)
    data = _parse(raw)
    cur = int(st.get("turn") or 0)
    return {
        "kind": "vision",
        "brief": str(data.get("brief", ""))[:120],
        "focus": [str(f)[:40] for f in (data.get("focus") or [])][:3],
        "base_turn": cur,
        "generated_turn": cur,
    }


def _parse(raw: str) -> dict:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"brief": raw[:120].strip(), "focus": []}
    if not isinstance(data, dict):
        return {"brief": str(data)[:120], "focus": []}
    return data


def write_vision(session_dir: Path, vision: dict) -> None:
    (session_dir / "plan.json").write_text(
        json.dumps(vision, ensure_ascii=False, indent=1), encoding="utf-8")


def read_vision(session_dir: Path) -> dict | None:
    p = session_dir / "plan.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return d if isinstance(d, dict) and d.get("kind") == "vision" else None


def vision_expired(vision: dict | None, cur: int, span: int = VISION_SPAN) -> bool:
    if not vision:
        return False
    return cur - int(vision.get("generated_turn") or 0) >= span
