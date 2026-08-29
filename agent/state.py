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
        f"/外点{n.get('diplomacy_points','?')}/稳{n.get('stability','?')}"
        f"/同化{len(n.get('assimilates') or [])}/战争分{n.get('war_score','?')}"
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
                 f"低稳省x{len(st.get('low_stability_list') or [])} "
                 f"核心省{stab.get('core','?')}/{stab.get('no_core','?')}非核心")
    treaties = st.get("treaties") or {}
    treaty_line = "条约: " + " ".join(f"civ{k}({v})" for k, v in treaties.items()) if treaties else ""
    wars = st.get("wars") or []
    war_line = ("战争: " + " ".join(f"w{agg_val}→{df_val}" for w in wars
                                    for agg_val, df_val in [(w.get('agg'), w.get('def'))])) if wars else ""
    if war_line and st.get("war_score_res"):
        ws = st["war_score_res"]
        war_line += f"（分数 我{ws.get('mine', ws.get('agg', '?'))}/敌{ws.get('theirs', ws.get('def', '?'))}）"
    flank = st.get("front_lines") or []
    front_line = ("前线: " + " ".join(
        f"省{f.get('from')}→省{f.get('to')}(civ{f.get('civ')},我{f.get('my_units')}兵/敌{f.get('enemy_units')}兵)"
        for f in flank[:8])) if flank else ""
    return (
        f"T{st.get('turn')} 日期{st.get('date','?')} 我civ{st.get('my_civ','?')} "
        f"金{st.get('money')} 省{st.get('provinces')} "
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


RISK_RATIO = 1.2


def threat_scan(st: dict) -> dict | None:
    """War-risk scan (2026-08-29 user feedback: agent got wiped out).

    A hostile (negative relation or already warring) neighbor whose army
    exceeds ours by RISK_RATIO is a pre-emptive window: act (declare war /
    stabilize relations), never turtle.
    """
    try:
        me = int(st.get("units") or 0)
    except (TypeError, ValueError):
        return None
    if me <= 0:
        return None
    for n in st.get("neighbors", []):
        try:
            un = int(n.get("units") or 0)
        except (TypeError, ValueError):
            continue
        rel = n.get("relation") or 0
        hostile = bool(n.get("war")) or (isinstance(rel, (int, float)) and rel < 0)
        if un >= me * RISK_RATIO and hostile:
            return {"civ_id": n.get("civ_id"), "units": un, "mine": me,
                    "ratio": round(un / me, 2), "war": bool(n.get("war"))}
    return None


def victory_progress(st: dict, session_dir: Path | None = None) -> str:
    """Resident win-oriented context block (2026-08-29 user requirement).

    Every decision must see: tech progress, territory standing vs biggest
    neighbor, per-neighbor force ratio, recent force/territory trend and the
    terminal signal — so the LLM plans toward a win, not just accumulation.
    """
    parts = ["【胜利进展】"]
    my = st.get("provinces")
    tech = st.get("my_tech")
    parts.append(f"科技={tech or '?'}（VICTORY_TECHNOLOGY 未在 /state 暴露，以我方实际科技为准）" if tech is not None
                 else "科技=?（胜利门槛未暴露）")
    nbs = st.get("neighbors") or []
    big = max(nbs, key=lambda n: (n.get("provinces") or 0), default=None)
    if big:
        parts.append(f"领土: 我{my}省 vs 最强{civ_big(big)} {big.get('provinces')}省"
                     f"（省数比={round((my or 0) / max(big.get('provinces') or 1, 1), 2)}）")
    my_units = int(st.get("units") or 0)
    if my_units > 0:
        ratios = ", ".join(
            "civ{}:{}×{}".format(n.get("civ_id"), round((n.get("units") or 0) / my_units, 2),
                                 "交战" if n.get("war") else "敌" if (n.get("relation") or 0) < 0 else "")
            for n in nbs if isinstance(n, dict) and n.get("civ_id") is not None)
        if ratios:
            parts.append(f"邻国防务比(军): {ratios}")
    trend = _force_trend(session_dir, 9)
    if trend:
        parts.append(trend)
    ge = st.get("game_end")
    ended = ge is True or (isinstance(ge, dict) and ge.get("ended") is True)
    parts.append("终局信号: 无" if not ended else "终局信号: 已终局(停止行动)")
    bgt = st.get("budget") or {}
    if bgt:
        def _pct(v):
            return "?" if v is None else f"{round(float(v) * 100)}%"
        parts.append(f"预算(可调): 税{_pct(bgt.get('taxation'))} 商品{_pct(bgt.get('goods'))} "
                     f"研究{_pct(bgt.get('research'))} 投资{_pct(bgt.get('investments'))}")
    return "；".join(parts)


def _force_trend(session_dir: Path | None, limit: int = 9) -> str:
    """Compact province/units trend from the newest turns.jsonl records."""
    if session_dir is None:
        return ""
    path = session_dir / "turns.jsonl"
    if not path.exists():
        return ""
    pts = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            s = d.get("state") or {}
            if "provinces" in s and isinstance(s["provinces"], int):
                pts.append((int(s.get("turn", 0)), int(s["provinces"]), int(s.get("units") or 0)))
    if not pts:
        return ""
    pts = pts[-limit:]
    t0, p0, u0 = pts[0]
    t1, p1, u1 = pts[-1]
    span = max(t1 - t0, 1)
    dprov = p1 - p0
    dun = u1 - u0
    seq = "→".join(str(p) for _, p, _ in pts[:6])
    return (f"趋势(T{t0}→T{t1}): 省 {seq}（净{p1 - p0:+d}）, 军 {u0}→{u1}（净{dun:+d}）, "
            f"均每回合省{round(dprov / span, 2)}/军{round(dun / span, 0):.0f}")


def civ_big(n: dict) -> int:
    return n.get("civ_id") or -1


def extract_ledger(st: dict) -> dict:
    """Resource budget line input (FR-017①): stock + per-turn income (if exposed).

    T036 alignment: gateway /state income now emits the contract shape
    {gold_in, gold_out, balance, diplo_delta} (bridge) or the legacy
    {gold, move, diplo, tech} keys — both are accepted; per-turn gold is the
    net (gold_in - gold_out), diplo uses diplo_delta.
    """
    inc = st.get("income") or {}
    income = None
    if inc:
        gold = inc.get("gold")
        if gold is None and ("gold_in" in inc or "gold_out" in inc):
            try:
                gold = int(inc.get("gold_in") or 0) - int(inc.get("gold_out") or 0)
            except (TypeError, ValueError):
                gold = inc.get("balance")
        income = {
            "gold": gold,
            "move": inc.get("move"),
            "diplo": inc.get("diplo_delta", inc.get("diplo")),
            "tech": inc.get("tech"),
        }
    return {
        "gold": st.get("money"),
        "move_pts": st.get("move_points"),
        "diplo_pts": st.get("diplomacy_points"),
        "tech_pts": st.get("tech_points"),
        "income": income,
    }


def _q(v) -> str:
    return "?" if v is None or v == "" else str(v)


def ledger_line(ledger: dict) -> str:
    inc = ledger.get("income")
    inc_s = ""
    if inc:
        inc_s = ("(收金{}/点{}/外{}/技{}/回合)".format(
            _q(inc.get("gold")), _q(inc.get("move")), _q(inc.get("diplo")), _q(inc.get("tech"))))
    return "【资源台账】金{} {}行动点{} 外交点{} 科技点{}".format(
        _q(ledger.get("gold")), inc_s,
        _q(ledger.get("move_pts")), _q(ledger.get("diplo_pts")), _q(ledger.get("tech_pts")))
