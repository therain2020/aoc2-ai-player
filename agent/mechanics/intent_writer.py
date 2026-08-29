"""Harness intent-decomposer: brief/threat promises -> capability steps -> plan actions.

2026-08-29 user requirement: LLM writes "挑拨/联合统治/预算整形" into the brief
but forgets the engine calls. This injects them into the 10-turn plan by:
  1. detecting intent keywords (brief + danger note),
  2. resolving parameters (civ ids from text/neighbors, budget gates),
  3. appending capability steps (agent/mechanics/capabilities.py) into turns,
  4. skipping anything the plan already contains (no duplicates, no budget overruns).
"""
from __future__ import annotations

import re

from agent.mechanics import capabilities

#: intent -> keywords. Capability steps are sourced from capabilities.CAPABILITIES.
INTENT_KEYWORDS = {
    "INCITE_WAR": ("挑拨", "互斗", "买战争", "渔翁"),
    "COALITION_WAR": ("联合阵线", "夹击", "联合围剿"),
    "ALLEGIANCE_CHAIN": ("联盟链", "联合统治", "合并提议", "互保"),
    "BUDGET_TUNE": ("预算", "税收", "投入占比", "财政"),
    "DEFEND_CORE": ("防御", "要塞化", "守备", "被入侵", "全面防御"),
    "LOAN": ("贷款", "融资"),
    "DOMINATE": ("吞并", "征服", "扩张", "宣战"),
}

#: capabilities that need no external params at all
_NO_TARGET = {"BUDGET_TUNE"}


def detect_intents(text: str) -> list[str]:
    found = []
    for intent, kws in INTENT_KEYWORDS.items():
        if any(k in (text or "") for k in kws):
            found.append(intent)
    return found


def _civ_ids(text: str) -> list[int]:
    return [int(m) for m in re.findall(r"civ(\d{1,5})", text or "")]


def resolve_params(intent: str, st: dict, text: str) -> dict:
    cis = _civ_ids(text)
    nbs = st.get("neighbors") or []

    def pick(key):
        if cis:
            return cis[0]
        if not nbs:
            return None
        if key == "big":
            return max(nbs, key=lambda n: (n.get("provinces") or 0)).get("civ_id")
        if key == "second":
            s = sorted(nbs, key=lambda n: (n.get("provinces") or 0), reverse=True)
            return s[1].get("civ_id") if len(s) > 1 else s[0].get("civ_id")
        if key == "big_relation":
            return max(nbs, key=lambda n: (n.get("relation") or 0)).get("civ_id")
        if key == "weak":
            return min(nbs, key=lambda n: (n.get("units") or 9e9)).get("civ_id")
        return cis[0] if cis else None

    gold = int(st.get("money") or 0)
    target = (pick("big") if intent in ("INCITE_WAR", "COALITION_WAR") else
              (pick("big_relation") if intent == "ALLEGIANCE_CHAIN" else pick("weak")))
    against = (cis[1] if len(cis) > 1 else pick("second"))
    return {
        "gold": max(500, min(gold // 10, 2000)),
        "target": target,
        "against": against,
    }


def _budget_ok(intent: str, st: dict) -> bool:
    gold = int(st.get("money") or 0)
    if intent in ("INCITE_WAR", "COALITION_WAR", "DEFEND_CORE", "LOAN"):
        if intent == "LOAN":
            return gold < 800
        if intent == "DEFEND_CORE":
            return gold > 300
        return gold > 500
    if intent == "ALLEGIANCE_CHAIN":
        return (int(st.get("diplomacy_points") or 0) >= 22) and gold > 500
    return True


#: rule-generated steps when a capability is missing or too generic for plans
_RULE_STEPS: dict[str, list[tuple[str, dict]]] = {
    "INCITE_WAR": [
        ("buy_war", {"target_civ_id": "target", "declare_war_on": "against", "gold": "gold"}),
    ],
    "COALITION_WAR": [
        ("coalition_war", {"target_civ_id": "target", "coalition_against": "against", "gold": "gold"}),
    ],
    "ALLEGIANCE_CHAIN": [
        ("guarantee_independence", {"target_civ_id": "target"}),
        ("military_access_ask", {"target_civ_id": "target"}),
        ("offer_alliance", {"target_civ_id": "target"}),
        ("union_proposal", {"target_civ_id": "target"}),
    ],
    "BUDGET_TUNE": [
        ("set_budget", {"tax_pct": 45, "goods_pct": 30, "research_pct": 15, "invest_pct": 20}),
    ],
    "DEFEND_CORE": [
        ("construct", {"building_type": "fort", "province_id": "border_prov"}),
        ("send_gift", {"target_civ_id": "target", "gold": "gold"}),
    ],
    "LOAN": [
        ("loan", {"gold": "gold", "duration": 12}),
    ],
    "DOMINATE": [
        ("declare_war", {"target_civ_id": "target"}),
        ("move_army", {"from_province": "front_prov", "to_province": "target_prov", "count": 300}),
        ("assimilate", {"province_id": "target_prov", "num_of_turns": 12}),
    ],
}


def inject(plan: dict, intents: list[str], st: dict, brief: str) -> list[str]:
    """Append capability steps into plan turns. Returns the injected summary."""
    notes: list[str] = []
    existing = {(a.get("action"), a.get("target_civ_id")) for t in plan.get("turns", [])
                for a in t.get("actions", [])}
    slot = 1
    for intent in intents:
        if intent in _NO_TARGET:
            pass
        if not _budget_ok(intent, st):
            continue
        params = resolve_params(intent, st, brief)
        steps = _RULE_STEPS.get(intent, [])
        for i, (action, tmpl) in enumerate(steps):
            real = {}
            for k, v in tmpl.items():
                if v in params:
                    real[k] = params[v]
                elif v == "border_prov":
                    real[k] = _border_province(st)
                elif v in ("front_prov", "target_prov"):
                    real[k] = _front_province(st, params.get("target"))
                elif v == "gold":
                    real[k] = params.get("gold", 500)
                else:
                    real[k] = v
            if (action, real.get("target_civ_id")) in existing:
                continue
            turns = plan.get("turns", [])
            if not turns:
                continue
            idx = i % len(turns)
            turns[idx].setdefault("actions", []).append({"action": action, **real})
            existing.add((action, real.get("target_civ_id")))
            notes.append(f"{intent}:{action}")
    return notes


def _border_province(st: dict) -> int:
    for n in st.get("neighbors", []):
        bp = n.get("border_provinces")
        if bp and isinstance(bp, list) and bp:
            return int(bp[0])
    provs = st.get("my_provinces") or [0]
    return int(provs[0]) if provs else 0


def _front_province(st: dict, target: int | None) -> int:
    for f in st.get("front_lines") or []:
        if f.get("civ") == target:
            return int(f.get("from") or 0)
    return _border_province(st)


def enrich_actions(actions: list[dict], text: str, st: dict,
                   danger: dict | None = None) -> list[str]:
    """R007: inject immediately into a single-turn decision's action list."""
    notes: list[str] = []
    if not actions:
        return notes
    existing = {(a.get("action"), a.get("target_civ_id")) for a in actions}
    intents = detect_intents(text)
    if danger:
        intents = _preempt_intent(intents, {"turns": [{"actions": actions}]}, danger, st)
    for intent in intents:
        if not _budget_ok(intent, st):
            continue
        params = resolve_params(intent, st, text)
        steps = _RULE_STEPS.get(intent, [])
        for action, tmpl in steps[:2]:          # 单回合注入 ≤2 步（焦点优先）
            real = {}
            for k, v in tmpl.items():
                if v in params:
                    real[k] = params[v]
                elif v == "border_prov":
                    real[k] = _border_province(st)
                elif v in ("front_prov", "target_prov"):
                    real[k] = _front_province(st, params.get("target"))
                elif v == "gold":
                    real[k] = params.get("gold", 500)
                else:
                    real[k] = v
            if (action, real.get("target_civ_id")) in existing:
                continue
            actions.append({"action": action, **real})
            existing.add((action, real.get("target_civ_id")))
            notes.append(f"{intent}:{action}")
    return notes


def enrich(plan: dict, brief: str, st: dict, danger: dict | None = None) -> list[str]:
    """Full harness correction pass: DANGER preempt + intent detection + injection."""
    text = str(brief or "")
    if danger:
        text += f" 危险信号 civ{danger.get('civ_id')}"
    intents = detect_intents(text)
    if danger:
        intents = _preempt_intent(intents, plan, danger, st)
    return inject(plan, intents, st, text)


def _preempt_intent(intents: list[str], plan: dict, danger: dict, st: dict) -> list[str]:
    """Threat (1.5x+) forces PREEMPT steps unless the plan already responds."""
    mine = int(st.get("units") or 0)
    enemy = int(danger.get("units") or 0)
    has = any(a.get("action") in ("declare_war", "send_gift", "improve_relations",
                                  "buy_war", "coalition_war")
              for t in plan.get("turns", []) for a in t.get("actions", []))
    if has:
        return intents
    if "INCITE_WAR" in intents and mine < enemy * 0.8:
        return intents   # too weak to preempt; incitement already preferred
    key = ("danger_preempt" if mine >= enemy * 1.1 else "danger_stabilize")
    _RULE_STEPS[key] = ([("declare_war", {"target_civ_id": "target"})]
                        if mine >= enemy * 1.1 else
                        [("send_gift", {"target_civ_id": "target", "gold": 300}),
                         ("improve_relations", {"target_civ_id": "target"})])
    intents = [key] + intents
    return intents
