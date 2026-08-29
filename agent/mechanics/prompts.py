"""Prompt assembly (T028): batch-plan & war-branch system prompts.

Three layers:
- FR-017① resource budget line: caller injects ledger_line() into the user ctx
  each call (per-turn stock + income); the system prompt states the budget rule.
- FR-017③ tactic guidance: built from the VERIFIED mechanics catalog only
  (constitution VII / SC-009: prompts must not reference unverified entries).
- FR-017①-④ decision principles: five resource cost classes, decision order,
  baseline tactic guidance, win-condition service.
"""
from __future__ import annotations

from agent.actions import ACTION_SPEC, actions_prompt_spec
from agent.mechanics import catalog


def _known_ops(ops: list[str]) -> tuple[list[str], int]:
    known = [o for o in ops if o in ACTION_SPEC]
    return known, len(ops) - len(known)


def mechanic_guidance(*ids: str) -> str:
    """Guidance snippet for given (default: all) VERIFIED mechanics.

    Phase ops that are not yet in ACTION_SPEC are marked so the prompt does not
    invite unknown actions (they land as T034/T035 and the marker disappears).
    """
    mids = ids or sorted(catalog.verified_ids())
    lines = []
    for mid in mids:
        e = catalog.entry(mid)
        if e is None or not catalog.is_verified(mid):
            continue
        parts = []
        for p in e.get("phases", []):
            known, missing = _known_ops(p.get("ops", []))
            marker = f"(待动作#{missing})" if missing else ""
            parts.append(f"{p['phase']}({'+'.join(known)}{marker})")
        trigger = (e.get("trigger") or "").split("；")[0]
        lines.append(f"- {mid}（{e.get('doc_ref', '')}）: {trigger}；阶段: {'；'.join(parts)}")
    return "\n".join(lines)


def plan_batch_spec() -> str:
    """Batch-plan mode spec: 10-turn {brief, turns[...]} with tactic_ref + principles."""
    return (
        "【批量计划模式】输出 JSON {brief: 总体方针一句话, turns: [10 个元素]}。"
        "每个 turn 元素: {offset: 回合序号(1..10), actions: [动作数组], note: 本回合一句话计划, "
        "tactic_ref: 可选的机制 id（见下方机制引导）}。\n"
        "动作格式与单回合一致（见可用动作表）。前几回合通常先征兵/投资/投科技点，中后期再进攻；"
        "相邻回合的动作要衔接（如先征兵后进攻需分回合）；科技点只在第一回合用完（技术效果持续）；"
        "所有动作要符合当前的战略档位。\n"
        "决策顺序（FR-017②）：先读【资源台账】存量与每回合收入 → 评估邻国国力"
        "（省份/军队/人口/金币/科技，结合关系：盟友不攻、略强先发展、全面碾压才宣战）→ 再配置动作。\n"
        "成本四原则（FR-017）：①动作按资源五分类（查询零成本/金/行动点/外交点/多资源），"
        "每回合花费必须 ≤ 台账预算；②先花不衰减资源（行动点），金币保底 ≥1000；"
        "③机制战术按下方引导触发，不硬编码；④一切决策服务获胜条件。\n"
        "机制引导（仅列出已验证机制）:\n" + mechanic_guidance() + "\n"
        "引擎规则（冷却）：①投资 invest/investDev 同省持续 4 回合窗口，同省间隔≥4回合，建议各省轮投；"
        "②建造 construct 完工周期约 2-3 回合，同建筑未完工不可重复建；③征兵每省当回合可批量一次，"
        "数量受可征兵上限（人口）与行动点约束；④迁都 move_capital 有 50 回合锁定，只可一次；"
        "⑤若金币<1500，只征兵/投科技点，不投资（保留金库）。\n"
        "科技点按当前阶段投放，不机械全倒：战争/备战→military_upkeep、research；和平→taxation、"
        "eco_growth、production；人口紧张→pop_growth；殖民地扩张→colonization；administration 按需。"
        "各类封顶：25/25/25/25/20/30/30/15，封顶后换下一类。"
    )


def build_plan_system() -> str:
    return (
        "直接输出JSON，禁止输出任何思考过程或解释。你是《文明时代2》的战略玩家，"
        "目标：安全扩张（先发展内政军备，实力超过邻国再宣战）；一切决策服务获胜条件。\n\n"
        + actions_prompt_spec()
        + "\n\n"
        + plan_batch_spec()
    )


def build_war_system() -> str:
    return (
        "直接输出JSON（{actions:[...], brief:\"...\"}），禁止任何思考过程或解释。"
        "你是正在交战中的军队统帅。每回合 1-3 个动作，参考【前线】数据："
        "move_army 只能从前线我方可攻击省（from）移动到相邻敌省（to）——"
        "我方前线兵力大于敌省时进攻吞并（moveArmy 到敌省会触发战斗），"
        "前线兵力劣势时优先征兵补充、集结防守；整体劣势严重时 peace_treaty 求和止损"
        "（向目标交战方发出停战提议，等待对方接受）。不要投资/建设/结盟。\n"
        "机制引导（战争）:\n" + mechanic_guidance("war_cycle") + "\n" + actions_prompt_spec()
    )


def plan_turn_closing(cur: int) -> str:
    return (f"\n当前回合 {cur}。请一次性规划未来 10 回合（当前回合算第 1 回合）；"
            "brief 必须写明我方 vs 最强邻国的国力对比判断。")


def war_turn_closing() -> str:
    return ("\n【战争状态】当前正与邻国交战。请给出下一回合的战争操作（1-3 个动作），重点："
            "推进军队到前线、征募新兵、必要时和谈；僵局判定：最后交火>39/49+回合无占领/"
            "战争>299 → peace_treaty 止损。")
