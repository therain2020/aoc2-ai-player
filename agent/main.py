"""M2 batch-plan agent: one LLM call plans 10 turns; re-plan only on
emergency (territory loss or user-driven strategy change).

Usage:
    python -m agent.main                          # uses config.yaml
    python -m agent.main --max-plans 0            # 0 = unlimited planning rounds
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import yaml  # noqa: E402

from agent.actions import (  # noqa: E402
    execute, parse_actions, parse_plan, result_ok, SKILL_CAPS, ActionError,
)
from agent.bridge_client import wait_until_up, BridgeError  # noqa: E402
from agent.llm import create_provider  # noqa: E402
from agent.llm.base import LLMError  # noqa: E402
from agent.state import (  # noqa: E402
    build_history, build_turn_context, extract_ledger, ledger_line, threat_scan,
    victory_progress,
)
from agent.mechanics import gears as mech_gears  # noqa: E402
from agent.mechanics import phases as mech_phases  # noqa: E402
from agent.mechanics import prompts as mech_prompts  # noqa: E402
from agent.messages import (  # noqa: E402
    decision_types, fixed_types, ignore_types, resolve_params, FIXED_RULES,
    split_types,
)
from agent.context_store import CtxStore  # noqa: E402
from recorder.session import create_session  # noqa: E402

CONFIG_GAME_ROOT = ""

WAR_SYSTEM_PROMPT = mech_prompts.build_war_system()


def load_config(path: str) -> dict:
    cfg_path = Path(path)
    if not cfg_path.exists():
        print(f"config not found: {cfg_path} (copy config.yaml.template to config.yaml)")
        sys.exit(2)
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


_TECH_ORDER = ("research", "production", "eco_growth", "military_upkeep",
               "taxation", "pop_growth", "administration", "colonization")


def _auto_invest_tech(bridge, st):
    """Engine-level fallback: spend all remaining tech points every turn.

    T037: skip categories already at their cap (docs/mechanics.md M-TECH
    SKILL_CAPS) instead of probing the engine to discover the limit.
    """
    pts = int(st.get("tech_points", 0) or 0)
    if pts <= 0:
        return
    skills = st.get("skills") or {}
    spent = 0
    for cat in _TECH_ORDER:
        if pts <= 0:
            break
        if int(skills.get(cat, 0) or 0) >= SKILL_CAPS.get(cat, 99):
            continue
        r = bridge.invest_tech(cat, pts)
        if result_ok(r):
            done = 0
            try:
                log = r.strip()
                if log.startswith("{"):
                    log = json.loads(log).get("log", "")
                done = int(log.split("|")[-1])
            except (ValueError, IndexError):
                pass
            if done > 0:
                spent += done
                pts -= done
                continue
        r1 = bridge.invest_tech(cat, 1)
        ok1 = result_ok(r1) and str(r1).strip().endswith("|1")
        if not ok1:
            break
        spent += 1
        pts -= 1
        pts = 0  # category capped; stop
    if spent:
        bridge.toast(f"科技点自动投放 {spent}")


def read_strategy(game_root: str) -> str:
    p = Path(game_root) / "aoc2_strategy.txt"
    try:
        if p.exists():
            try:
                t = p.read_text(encoding="utf-8").strip()[:2000]
            except UnicodeDecodeError:
                t = p.read_text(encoding="gbk", errors="replace").strip()[:2000]
            return t
    except OSError:
        pass
    return ""


def read_plan(session_dir: Path):
    p = session_dir / "plan.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def write_plan(session_dir: Path, plan: dict):
    (session_dir / "plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")


def round_append(session_dir: Path, record: dict):
    with open(session_dir / "turns.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def handle_messages(bridge, ctx_store, st) -> str:
    """Three-kind message dispatch (user principle 2026-08-29):
    - decision -> agent decides (never auto-respond); re-plan happens upstream
    - fixed    -> run the rule action (e.g. civilize self), then clear bundle
    - ignore   -> context record only, then clear bundle
    Returns "decision" or "auto" (fixed/ignore both land in auto class here).
    """
    mtypes = st.get("msg_types", "")
    dtypes = decision_types(mtypes)
    if dtypes:
        ctx_store.add_event("decision", ",".join(dtypes[:8]))
        print(f"DECISION MSG [{dtypes}] -> agent decides (no auto-respond)", flush=True)
        return "decision"
    for m in fixed_types(mtypes):
        rule = FIXED_RULES.get(m)
        if not rule:
            continue
        try:
            params = resolve_params(rule["params"], st)
            r = getattr(bridge, rule["action"])(**params)
            print(f"FIXED MSG {m} -> {rule['action']} {params}: {str(r)[:110]}", flush=True)
            ctx_store.add_event("fixed", f"{m}:{str(r)[:60]}")
        except Exception as e:
            print(f"FIXED MSG {m} skipped ({e})", flush=True)
    ctx_store.sync_neighbors(st.get("neighbors", []))
    itypes = ignore_types(mtypes)
    if itypes:
        ctx_store.add_event("ignore", ",".join(itypes[:12]))
    bridge.respond_messages()
    print(f"AUTO MSG [{mtypes}] -> context only", flush=True)
    return "auto"


def set_msg_lines(ctx_store, st) -> str:
    lines = []
    rel = ctx_store.relation_line({n.get("civ_id") for n in st.get("neighbors", []) if n.get("civ_id") is not None})
    if rel:
        lines.append(rel)
    dec = ctx_store.decision_summary()
    if dec:
        lines.append(dec)
    return "\n".join(lines) + "\n" if lines else ""


def str_sig(s: str) -> str:
    import hashlib
    return hashlib.md5((s or "").encode("utf-8")).hexdigest()


def _plan_addresses(plan: dict, thr: dict) -> bool:
    """Does the current plan already respond to the threat (war/gift/relations)?"""
    target = thr.get("civ_id")
    for t in plan.get("turns", []):
        for a in t.get("actions", []):
            name = a.get("action")
            if name in ("declare_war", "send_gift", "improve_relations",
                        "buy_war", "coalition_war") and a.get("target_civ_id") == target:
                return True
    return False


def _pause_status(game_root: str) -> str:
    """Pause source summary at startup — NEVER auto-delete (user pauses are sacred)."""
    p = Path(game_root) / "aoc2_pause.txt"
    try:
        if not p.exists():
            return ""
        first = p.read_text(encoding="utf-8", errors="replace").splitlines()[0]
        return f"pause file detected: {first or '(no marker)'} — agent waits; resume by deleting it"
    except OSError:
        return ""


class WarTracker:
    """T030 M-WAR parametrization: track stalemate signals per war episode.

    Engine AI peace triggers (docs/mechanics.md:77): last battle > 39 turns
    (no battle > 19), no conquest for 49 turns, war > 299 turns.
    """

    def __init__(self):
        self.start: int | None = None
        self.last_battle: int | None = None
        self.last_conquest: int | None = None

    def on_turn(self, turn: int):
        if self.start is None:
            self.start = turn

    def note_results(self, turn: int, results: list, prev_provinces: int, now_provinces: int):
        for r in results:
            if r.get("action") == "move_army" and result_ok(r.get("result", "")):
                self.last_battle = turn
        if now_provinces > prev_provinces:
            self.last_conquest = turn

    def stalemate_flags(self, cur: int) -> list[str]:
        flags = []
        if self.start is None:
            return flags
        if self.last_battle is None:
            if cur - self.start >= 19:
                flags.append(f"开战 {cur - self.start} 回合无交火（≥19）")
        elif cur - self.last_battle >= 39:
            flags.append(f"最后交火距今 {cur - self.last_battle} 回合（≥39）")
        if self.last_conquest is not None and cur - self.last_conquest >= 49:
            flags.append(f"已 {cur - self.last_conquest} 回合无占领（≥49）")
        if cur - self.start > 299:
            flags.append(f"战争已 {cur - self.start} 回合（>299）")
        return flags


#: transient views the engine auto-confirms / fast-forwards (FR-013);
#: agent-side just waits briefly (T045 known-transition list).
TRANSITION_PREFIXES = ("NextPlayerTurn", "TURN_ACTIONS", "LOAD_", "StartTheGame")


def chat_with_fallback(provider, system: str, ctx: str, hint: str = "") -> str:
    """One retry on LLMError (T043); raises LLMError if both attempts fail."""
    try:
        return provider.chat(system, ctx, temperature=0.3, max_tokens=8000)
    except LLMError:
        return provider.chat(system, ctx + "\n" + (hint or "上次系统调用返回错误，请重试。"),
                             temperature=0.3, max_tokens=8000)


def front_assessment(front_lines: list, stale: list[str]) -> str:
    """Front-line scoring + attack discipline (single-province >=10 to attack)."""
    if not isinstance(front_lines, list) or not front_lines:
        return "前线评估: 暂无前线信息（敌军远守或未接壤）——按征兵集结处理。"
    lines = []
    for f in front_lines[:8]:
        my = int(f.get("my_units") or 0)
        en = int(f.get("enemy_units") or 0)
        if my >= 10 and my > en:
            rec = "进攻吞并（碾压）"
        elif my > 0:
            rec = "对峙防守（兵力不足不打）"
        else:
            rec = "征兵补充"
        lines.append(f"· 省{f.get('to')}(敌civ{f.get('civ')}): 我{my}/敌{en} → {rec}")
    head = "前线评分: \n" + "\n".join(lines)
    disc = "\n攻击纪律: 单省我方兵力≥10 且 > 敌省时才进攻；劣势只集结/征兵/防守。"
    stal = ("\n⚠ 僵局信号: " + "；".join(stale) + "\n建议启用 peace_treaty 止损（向交战方求和，等待对方接受）。") if stale else ""
    return head + disc + stal


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(REPO / "config.yaml"))
    ap.add_argument("--session-dir", default=None)
    ap.add_argument("--max-plans", type=int, default=0, help="0 = unlimited plan cycles")
    args = ap.parse_args()

    config = load_config(args.config)
    game_root = config.get("game", {}).get("root", os.environ.get("AOC2_GAME_ROOT", ""))
    if not game_root:
        print("config game.root missing; edit config.yaml")
        sys.exit(2)
    global CONFIG_GAME_ROOT
    CONFIG_GAME_ROOT = game_root
    note = _pause_status(game_root)
    if note:
        print(note, flush=True)

    ctx_store = CtxStore(Path(game_root) / "aoc2_context.json")

    provider = create_provider(config)
    print("LLM provider ready")
    try:
        bridge = wait_until_up()
    except BridgeError as e:
        print(f"bridge not reachable: {e}")
        sys.exit(3)
    print("AgentBridge connected:", bridge.state())

    base_dir = args.session_dir or config.get("session", {}).get("dir", "./sessions")
    session_dir = create_session(base_dir, "agent", f"run-{datetime.now().strftime('%H%M%S')}")

    plan_cycles = 0
    planned_turn = 0          # planned last turn absolute id
    plan = None
    strategy_sig = ""
    last_executed = -1
    hud_last_push = 0.0
    last_war_turn = -1
    war_trk = WarTracker()
    prev_provinces = 0
    fail_streak = 0
    last_danger_replan = -99

    def record_skip(cur, phase, ledger, reason) -> None:
        """T043: LLM 失败/输出无效兜底——SKIP_TURN 确定性推进 + FAIL 标记；
        连续 3 回合 FAIL → 写暂停文件并告警（dashboard 可读 turns.jsonl 的 fail_reason）。"""
        nonlocal fail_streak
        fail_streak += 1
        print(f"SKIP_TURN (streak {fail_streak}): {reason}", flush=True)
        round_append(session_dir, {
            "turn": cur, "ts": time.time(), "type": "skip",
            "mechanic_phase": phase.phase_id, "tactic_ref": phase.tactic_ref,
            "ledger": ledger, "decision": [], "results": [],
            "brief": "LLM 失败 → SKIP_TURN", "fail_reason": str(reason)[:120],
            "tokens": dict(provider.last_usage), "tokens_cum": dict(provider.total),
        })
        if fail_streak >= 3:
            import datetime
            (Path(game_root) / "aoc2_pause.txt").write_text(
                "#auto:3x-llm-failures " + datetime.datetime.now().isoformat(timespec="seconds")
                + "\nagent: 3 consecutive LLM failures", encoding="utf-8")
            print("ALERT: 3 consecutive LLM failures -> paused (aoc2_pause.txt, #auto marker); "
                  "resume by deleting the file", flush=True)
        try:
            _auto_invest_tech(bridge, st)
        except Exception:
            pass
        bridge.end_turn()
        time.sleep(4)

    try:
        while True:
            try:
                st = json.loads(bridge.state())
            except (json.JSONDecodeError, BridgeError):
                # bridge hiccup / transient malformed payload: back off, do not crash
                time.sleep(5)
                continue
            ts = st.get("turn_state")
            ge = st.get("game_end")
            ended = ge is True or (isinstance(ge, dict) and ge.get("ended") is True)
            if ended:
                print("[dbg] ended-gate", flush=True)
                time.sleep(10)
                continue
            if ts != "INPUT_ORDERS":
                known = bool(ts) and any(str(ts).startswith(p) for p in TRANSITION_PREFIXES)
                time.sleep(1.5 if known else 3.0)
                continue
            cur = st.get("turn", 0)
            # gate: only act on a real game (in-game view, or a played turn exists —
            # menu preview instances always report turn 1)
            if not st.get("in_game", False) and cur <= 1:
                print("[dbg] menu-gate", flush=True)
                time.sleep(4)
                continue
            if Path(game_root, "aoc2_pause.txt").exists():
                print("[dbg] pause-gate", flush=True)
                time.sleep(2)
                continue
            # keep balance/token HUD live even between plan executions
            if time.time() - hud_last_push > 10 and plan is not None:
                try:
                    uu = provider.last_usage
                    bal = provider.fetch_balance() if getattr(provider, "track_balance", False) else None
                    bridge.hud(line1=(f"余额 ¥{bal:.2f}" if bal is not None else "余额 --")
                               + f" ｜ Token 入{uu.get('prompt_tokens',0)} 出{uu.get('completion_tokens',0)}")
                    hud_last_push = time.time()
                except Exception:
                    pass
            if cur == last_executed:
                time.sleep(5)
                continue

            # US1 (T017): mechanic-phase recognition + resource ledger per turn
            phase = mech_phases.assess(st)
            ledger = extract_ledger(st)
            phase_note = f"【机制阶段】{phase.phase_id}"
            if phase.tactic_ref:
                phase_note += f"；战术引用: {phase.tactic_ref}"

            # at war: per-turn single-call war decisions (no batch plan)
            at_war = bool(st.get("wars")) or any(n.get("war") for n in st.get("neighbors", []))
            if at_war:
                if st.get("messages", 0) > 0:
                    kind = handle_messages(bridge, ctx_store, st)
                    if kind == "decision":
                        time.sleep(1)
                        continue
                if last_war_turn == cur:
                    time.sleep(5)
                    continue
                print(f"WAR TURN {cur}: single-call war decision", flush=True)
                war_trk.on_turn(cur)
                stale = war_trk.stalemate_flags(cur)
                assessment = front_assessment(st.get("front_lines", []), stale)
                history = build_history(session_dir)
                ctx = build_turn_context(st, history)
                strat = read_strategy(game_root)
                if strat:
                    ctx = f"【用户战略指示】{strat}\n" + ctx
                ctx = (f"{ledger_line(ledger)}\n{mech_prompts.budget_guard(ledger)}\n{phase_note}\n"
                       + set_msg_lines(ctx_store, st)
                       + ctx
                       + "\n" + assessment
                       + mech_prompts.war_turn_closing())
                try:
                    raw = chat_with_fallback(provider, WAR_SYSTEM_PROMPT, ctx)
                except LLMError as e:
                    record_skip(cur, phase, ledger, f"war llm: {e}")
                    continue
                try:
                    war_actions = parse_actions(raw)
                except (ActionError, json.JSONDecodeError) as e:
                    print(f"war action invalid ({e}), retrying once", flush=True)
                    try:
                        war_actions = parse_actions(chat_with_fallback(
                            provider, WAR_SYSTEM_PROMPT, ctx, "上次输出不合法，请严格按格式输出。"))
                    except (ActionError, json.JSONDecodeError, LLMError) as e2:
                        record_skip(cur, phase, ledger, f"war invalid x2: {e2}")
                        continue
                fail_streak = 0
                results = execute(bridge, war_actions)
                war_trk.note_results(cur, results, prev_provinces, st.get("provinces", 0))
                prev_provinces = st.get("provinces", 0)
                ok_n = sum(1 for r in results if result_ok(r["result"]))
                print(f"  war actions {ok_n}/{len(results)} ok: "
                      f"{[r['action'] for r in results]}", flush=True)
                bridge.toast(f"[战争回合{cur}] 已执行 {ok_n}/{len(results)}")
                round_append(session_dir, {
                    "turn": cur, "ts": time.time(), "type": "war",
                    "state": {k: st.get(k) for k in ("turn", "money", "provinces", "units")},
                    "mechanic_phase": phase.phase_id, "tactic_ref": phase.tactic_ref,
                    "ledger": ledger,
                    "decision": war_actions, "results": results,
                    "brief": "战争回合决策",
                    "tokens": dict(provider.last_usage), "tokens_cum": dict(provider.total),
                })
                last_war_turn = cur
                bridge.end_turn()
                time.sleep(4)
                continue

            # messages (three-kind model 2026-08-29):
            #   decision = needs agent judgement -> NEVER auto-respond, re-plan
            #   fixed    = rule action (civilize etc.) runs, then cleared
            #   ignore   = pure notification -> context only, cleared
            if st.get("messages", 0) > 0:
                kind = handle_messages(bridge, ctx_store, st)
                if kind == "decision":
                    plan = None          # fresh plan/decision this turn
                time.sleep(1)
                continue

            # strategy changed by user (PageUp/Insert)? -> re-plan immediately
            strat = read_strategy(game_root)
            s_sig = str_sig(strat)
            if plan is None or (strat and s_sig != strategy_sig):
                plan = None
                strategy_sig = s_sig

            # emergency checks: territory lost OR hostile army overtakes mine.
            # DANGER re-plans at most once per 3 turns, unless the current plan
            # does NOT address the threat (cooldown prevents LLM burn loops).
            thr = threat_scan(st)
            if plan is not None:
                base_prov = plan.get("base_provinces", 0)
                if cur > planned_turn and st.get("provinces", 0) < base_prov:
                    print(f"EMERGENCY: provinces {base_prov} -> {st.get('provinces')}, re-planning", flush=True)
                    plan = None
                if thr and (cur - last_danger_replan >= 3 or not _plan_addresses(plan, thr)):
                    print(f"DANGER: civ{thr['civ_id']} units {thr['units']} >= {thr['ratio']}x mine -> re-plan",
                          flush=True)
                    plan = None
                    last_danger_replan = cur

            if plan is None:
                plan_cycles += 1
                if args.max_plans and plan_cycles > args.max_plans:
                    print(f"reached max-plans={args.max_plans}, stopping")
                    break
                history = build_history(session_dir)
                ctx = build_turn_context(st, history)
                danger_note = ""
                if thr:
                    danger_note = (f"【危险信号】邻国 civ{thr['civ_id']} 军力 = 我方×{thr['ratio']}"
                                   f"（{thr['units']} vs {thr['mine']}）"
                                   f"{'，已交战' if thr['war'] else '，关系为敌'}——"
                                   "先发制人或送礼维稳，禁止躺平发展/缓慢备战。\n")
                if strat:
                    ctx = f"【用户战略指示】{strat}\n" + ctx
                ctx = (f"{ledger_line(ledger)}\n{mech_prompts.budget_guard(ledger)}\n{phase_note}\n"
                       + danger_note
                       + set_msg_lines(ctx_store, st)
                       + victory_progress(st, session_dir) + "\n"
                       + ctx
                       + mech_prompts.plan_turn_closing(cur))
                # gear-aware system prompt: current gear's engine-API policy injected
                plan_sys = mech_prompts.build_plan_system(mech_gears.gear_index(strat))
                try:
                    raw = chat_with_fallback(provider, plan_sys, ctx)
                except LLMError as e:
                    record_skip(cur, phase, ledger, f"plan llm: {e}")
                    continue
                try:
                    plan = parse_plan(raw)
                except (ActionError, json.JSONDecodeError) as e:
                    print(f"plan invalid ({e}), retrying once", flush=True)
                    try:
                        plan = parse_plan(chat_with_fallback(
                            provider, plan_sys, ctx, "上次输出不合法，请严格按格式输出。"))
                    except (ActionError, json.JSONDecodeError, LLMError) as e2:
                        record_skip(cur, phase, ledger, f"plan invalid x2: {e2}")
                        continue
                fail_streak = 0
                plan["base_provinces"] = st.get("provinces", 0)
                plan["start_turn"] = cur
                planned_turn = cur + len(plan["turns"]) - 1
                write_plan(session_dir, plan)
                try:
                    plines = []
                    for pt in plan["turns"]:
                        act = " ".join(a["action"] for a in pt["actions"])
                        plines.append(f"T+{pt['offset']} {pt.get('note','')[:36]} [{act}]")
                    plan_text = "\n".join(["未来计划: " + plan["brief"][:30]] + plines)
                    Path(game_root, "aoc2_plan.txt").write_text(plan_text, encoding="utf-8")
                    bridge.push_plan(plan_text)
                except Exception:
                    pass
                print(f"PLAN {plan['brief']} ({len(plan['turns'])} turns)", flush=True)
                round_append(session_dir, {
                    "turn": cur, "ts": time.time(), "type": "plan",
                    "mechanic_phase": phase.phase_id, "tactic_ref": phase.tactic_ref,
                    "ledger": ledger,
                    "brief": plan["brief"], "plan": [{"offset": t["offset"], "note": t.get("note", "")} for t in plan["turns"]],
                    "tokens": dict(provider.last_usage), "tokens_cum": dict(provider.total),
                })
                time.sleep(2)
                continue

            # execute the next planned turn (planned turn absolute id = start_turn + offset - 1)
            start_turn = plan.get("start_turn", cur)
            idx = 0
            while idx < len(plan["turns"]) and cur >= start_turn + plan["turns"][idx]["offset"] - 1:
                idx += 1
            if idx >= len(plan["turns"]):
                print("plan finished; re-planning", flush=True)
                plan = None
                time.sleep(2)
                continue
            entry = plan["turns"][idx]
            entry_actions = entry["actions"]
            print(f"--- executing turn {cur} (plan {entry['note'] or ''}) ---", flush=True)

            results = execute(bridge, entry_actions)
            ok_state = [r for r in results if result_ok(r["result"])]
            print(f"  executed {len(ok_state)}/{len(results)} ok", flush=True)
            balance = provider.fetch_balance() if getattr(provider, "track_balance", False) else None
            u = provider.last_usage
            t = provider.total
            token_toast = (f"Token 入{u.get('prompt_tokens',0)} 出{u.get('completion_tokens',0)}"
                           f" | 累计 {t.get('prompt_tokens',0)/1e6:.3f}M+{t.get('completion_tokens',0)/1e6:.3f}M")
            bridge.toast(f"[回合{cur}] {entry.get('note','')}")
            bridge.toast(token_toast)
            try:
                hist_lines = build_history(session_dir, limit=0).splitlines()
                bridge.hud(
                    line1=(f"余额 ¥{balance:.2f}" if balance is not None else "余额 --")
                          + f" ｜ Token 入{u.get('prompt_tokens',0)} 出{u.get('completion_tokens',0)}",
                    line2=f"T{cur} {entry.get('note','')}",
                    line3=hist_lines[-1] if hist_lines else "",
                    line4=hist_lines[-2] if len(hist_lines) > 1 else "",
                    line5=hist_lines[-3] if len(hist_lines) > 2 else "",
                )
            except Exception:
                pass
            round_append(session_dir, {
                "turn": cur, "ts": time.time(),
                "mechanic_phase": phase.phase_id, "tactic_ref": phase.tactic_ref,
                "ledger": ledger,
                "state": {k: st.get(k) for k in ("turn", "money", "provinces", "units", "move_points")},
                "neighbors": st.get("neighbors", []),
                "decision": entry_actions, "brief": entry.get("note", ""),
                "results": results, "plan_brief": plan.get("brief"),
                "tokens": dict(provider.last_usage), "tokens_cum": dict(provider.total),
                "balance": balance,
            })
            if not ok_state:
                print("turn fully failed; re-planning", flush=True)
                plan = None
            try:
                _auto_invest_tech(bridge, st)
            except Exception:
                pass
            bridge.end_turn()
            last_executed = cur
            print(f"turn {cur} done -> endTurn", flush=True)
            time.sleep(4)
    except KeyboardInterrupt:
        print("stopped by user")


if __name__ == "__main__":
    main()
