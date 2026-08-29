"""Turn context assembly for the LLM (from bridge /state + session history).

Token/cache strategy: history lines are appended-only (never rewritten) so the
provider's prefix cache keeps hitting; each line is aggressively compacted.
"""
import json
from pathlib import Path


def format_state_line(st: dict) -> str:
    neigh = ", ".join(
        f"civ{n['civ_id']}(省{n.get('provinces','?')}/军{n.get('units','?')}/人{n.get('population','?')}"
        f"/金{n.get('money','?')}/技{n.get('tech','?')}/关{n.get('relation','?')}"
        f"/都{n.get('capital','?')}/边{n.get('border_provinces','?')}"
        f"{'(同盟)' if n.get('allied') else ''}{'(交战!)' if n.get('war') else ''})"
        for n in st.get("neighbors", [])) or "无邻国"
    skills = st.get("skills") or {}
    skill_line = ("技能: 人口{} 经济{} 税{} 产{} 政{} 军费{} 研{} 殖{}".format(
        skills.get("pop_growth", 0), skills.get("eco_growth", 0), skills.get("taxation", 0),
        skills.get("production", 0), skills.get("administration", 0),
        skills.get("military_upkeep", 0), skills.get("research", 0), skills.get("colonization", 0)))
    detail_parts = []
    for pd in st.get("province_detail", []):
        detail_parts.append(f"省{pd['id']}(人{pd.get('pop','?')}/发{pd.get('dev','?')}/经{pd.get('econ','?')}"
                            f"/军{pd.get('army','?')}/堡{pd.get('fort','?')}"
                            f"{'/都' if pd.get('capital') else ''})")
    detail = ("我方省份: " + " ".join(detail_parts[:8])) if detail_parts else ""
    stab = st.get("stability") or {}
    stab_line = (f"稳定: 均满意{stab.get('hap_avg','?')} 最高革命风险{stab.get('rev_max','?')} "
                 f"核心省{stab.get('core','?')}/{stab.get('no_core','?')}非核心")
    treaties = st.get("treaties") or {}
    treaty_line = "条约: " + " ".join(f"civ{k}({v})" for k, v in treaties.items()) if treaties else ""
    wars = st.get("wars") or []
    war_line = ("战争: " + " ".join(f"w{agg_val}→{df_val}" for w in wars
                                    for agg_val, df_val in [(w.get('agg'), w.get('def'))])) if wars else ""
    flank = st.get("front_lines") or []
    front_line = ("前线: " + " ".join(
        f"省{f.get('from')}→省{f.get('to')}(civ{f.get('civ')},我{f.get('my_units')}兵/敌{f.get('enemy_units')}兵)"
        for f in flank[:8])) if flank else ""
    return (
        f"T{st.get('turn')} 日期{st.get('date','?')} 金{st.get('money')} 省{st.get('provinces')} "
        f"军{st.get('units')} 点{st.get('move_points')} 科技{st.get('my_tech','?')} "
        f"首都{st.get('capital','?')} 科技点剩{st.get('tech_points', '?')} 消息{st.get('messages')}\n"
        f"{skill_line}\n{detail}\n{stab_line}\n{treaty_line}\n{war_line}\n{front_line}\n邻国: {neigh}"
    )


def _compact_action(a: dict) -> str:
    name = a.get("action", "")
    short = {"declare_war": "宣", "recruit_army": "征", "move_army": "移",
             "invest": "投", "invest_dev": "展", "invest_tech": "技",
             "disband_army": "散", "move_capital": "都", "offer_alliance": "盟",
             "construct": "建"}
    params = ",".join(f"{k}={v}" for k, v in a.items() if k != "action")
    return f"{short.get(name, name)}{params}"


def build_history(session_dir: Path, limit: int = 0) -> str:
    """Append-only compact history. limit<=0 means keep everything (cache-friendly)."""
    path = session_dir / "turns.jsonl"
    if not path.exists():
        return "（无历史）"
    lines = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            acts = " ".join(_compact_action(a) for a in (d.get("decision") or []))
            brief = (d.get("brief") or "")[:24]
            lines.append(f"T{d.get('turn')} {brief} | {acts}")
    if limit and limit > 0 and len(lines) > limit:
        lines = lines[-limit:]
    return "\n".join(lines)


def build_turn_context(state: dict, history: str) -> str:
    st_line = format_state_line(state)
    province_ids = state.get("my_provinces", [])
    provs_ctx = "我方省ID: " + (",".join(map(str, province_ids[:30])) if province_ids else "无")
    l_line = ledger_line(extract_ledger(state))
    return f"{l_line}\n{st_line}\n{provs_ctx}\n历史:\n{history}"


def extract_ledger(st: dict) -> dict:
    """Resource budget line input (FR-017①): stock + per-turn income (if exposed)."""
    inc = st.get("income") or {}
    income = {k: inc.get(k) for k in ("gold", "move", "diplo", "tech")} if inc else None
    return {
        "gold": st.get("money"),
        "move_pts": st.get("move_points"),
        "diplo_pts": st.get("diplomacy_points"),
        "tech_pts": st.get("tech_points"),
        "income": income,
    }


def ledger_line(ledger: dict) -> str:
    inc = ledger.get("income")
    inc_s = ""
    if inc:
        inc_s = ("(收金{}/点{}/外{}/技{}/回合)".format(
            inc.get("gold", "?"), inc.get("move", "?"), inc.get("diplo", "?"), inc.get("tech", "?")))
    return "【资源台账】金{} {}行动点{} 外交点{} 科技点{}".format(
        ledger.get("gold", "?"), inc_s,
        ledger.get("move_pts", "?"), ledger.get("diplo_pts", "?"), ledger.get("tech_pts", "?"))
