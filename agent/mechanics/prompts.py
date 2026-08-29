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

from agent.actions import ACTION_SPEC, TECH_CATEGORIES, SKILL_CAPS, actions_prompt_spec
from agent.mechanics import catalog
from agent.mechanics.gears import GEAR_POLICY, gear_policy


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


def plan_batch_spec(gear_idx: int | None = None) -> str:
    """Batch-plan mode spec: 10-turn {brief, turns[...]} with tactic_ref + principles.

    gear_idx (1-6) injects the gear-execution policy (agent/mechanics/gears.py):
    which engine APIs the current gear intends to use and what is taboo.
    """
    gear_part = ""
    if gear_idx and gear_idx in GEAR_POLICY:
        gear_part = gear_policy(gear_idx) + "\n"
    return gear_part + (
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
        "决策消息回应：上下文出现【最近决策消息】时优先用对应动作回复——开化确认→"
        "civilize{target_civ_id=我方 civ}（确认体制转换，且消息有剩余回合，勿拖）；"
        "其余提议（和约/贸易/盟约等）在 accept/decline 动作面落地前保持克制。\n"
        "威胁与外交主动（2026-08-29 用户教训：防守龟缩会被灭）——从不'继续发展'式躺平：\n"
        "① 先发制人：任一战性邻国军力≥我方×1.2 且关系<0 → 立即再规划：要么抢先宣战（碾压其薄弱方向），"
        "要么送礼/改善关系维稳（send_gift/improve_relations），绝不坐等被灭；\n"
        "② 渔翁得利（FR-017③ baseline）：挑动两个相邻强国互斗（对 A 提好关系+对 B 支持叛军/羞辱制造间隙），"
        "等两强相争、胜者进入同化消耗期（低稳定省多、外交点流失）再对其突袭——小投入换最大领土；\n"
        "③ 强邻关系维持：对体量明显大于我方的邻国主动维持关系≥0（小额礼赠），避免被夹击孤立；"
        "保证至少一个邻国为友（结盟/NAP）。\n"
        "机制引导（仅列出已验证机制）:\n" + mechanic_guidance() + "\n"
        "引擎规则（冷却）：①投资 invest/investDev 同省持续 4 回合窗口，同省间隔≥4回合，建议各省轮投；"
        "②建造 construct 完工周期约 2-3 回合，同建筑未完工不可重复建；③征兵每省当回合可批量一次，"
        "数量受可征兵上限（人口）与行动点约束；④迁都 move_capital 有 50 回合锁定，只可一次；"
        "⑤若金币<1500，只征兵/投科技点，不投资（保留金库）。\n"
        "科技点按当前阶段投放，不机械全倒：战争/备战→military_upkeep、research；和平→taxation、"
        "eco_growth、production；人口紧张→pop_growth；殖民地扩张→colonization；administration 按需。"
        "各类封顶：" + "/".join(str(SKILL_CAPS[c]) for c in TECH_CATEGORIES) + "，封顶后换下一类。"
    )


def build_plan_system(gear_idx: int | None = None) -> str:
    return (
        "直接输出JSON，禁止输出任何思考过程或解释。你是《文明时代2》的战略玩家，"
        "目标：安全扩张（先发展内政军备，实力超过邻国再宣战）；一切决策服务获胜条件。\n\n"
        + actions_prompt_spec()
        + "\n\n"
        + plan_batch_spec(gear_idx)
    )


def build_war_system() -> str:
    return (
        "直接输出JSON（{actions:[...], brief:\"...\"}），禁止任何思考过程或解释。"
        "你是正在交战中的军队统帅——目标：打赢战争，不是维持现状。每回合动作数量不限，战争纪律：\n"
        "① 机动优先·高兵力省不闲置（用户 2026-08-29）：move_army 只能走【战场图】上的边"
        "（我邻/敌邻），引擎逐条执行——连续多段 move 一回合内完成。先看驻军最多的省：\n"
        "   - 它紧贴敌省且我≥10、我>敌 → 直接 move_army 进攻吞并；\n"
        "   - 它在后方 → 沿『我邻』前移到更靠前线/最缺兵的我方省（可多步连续移）；\n"
        "   - 它已在前沿但兵力压不住敌省（我≤敌）→ 集中之戒备/等征兵，不做无意义折返。\n"
        "② 前线进攻：我≥10 且>敌省才 move_army 吞并；劣势侧用①调兵增援，不硬啃；"
        "主力集中一条战线，勿分散。\n"
        "③ 动员：高兵力省已前压后、前线仍缺兵才动员（多省各一批，行动点定批次）；"
        "若【金库提示】写明金库<500——征兵动作会被规则拒绝，改用①调动，禁止重复签发征兵。\n"
        "④ 反击：敌人进入我方纵深省份（我方失去省）→ 立即用高兵力省反向夺回（move_army），"
        "或在其薄弱侧翼开辟新战线。\n"
        "⑤ 僵局/整体劣势：参考【危险信号】与战争分数（僵局 39/49/299 回合无进展）→ peace_treaty 止损。\n"
        "和谈回应：若【待处决策消息】含对方求和/和约（WeCanSignPeace/PeaceTreaty）——显式回应，不得无视："
        "我方优势（战争分≥+20）→ peace_treaty{target_civ_id} 接受锁定战果（避免拖泥带水，engine 自动分胜利点）；"
        "军力≥敌×2.5 且大胜（+70）→ 可继续碾压灭国（note 说明拒绝原因）；"
        "劣势/无胜算 → peace_treaty 止损。\n"
        "硬约束：actions **禁止为空数组**——必须至少 1 个动作（无事可做=1 个最小动作如集结/征兵/前线移动）。\n"
        "禁止投资/建设/结盟/慢速备战；【金库提示】为权衡信息（金库<500 时征兵会被拒，见③；军事移动不受限）。\n"
        "机制引导（战争）:\n" + mechanic_guidance("war_cycle") + "\n" + actions_prompt_spec()
    )


def build_vision_system() -> str:
    """FR-008 revised: 10-turn textual vision — direction only, NO per-turn actions."""
    return (
        "直接输出JSON，禁止任何思考过程或解释。你是《文明时代2》的战略家，"
        "为未来 10 回合拟定一个**文字愿景**（方向与目标，不含回合动作表）。输出仅：\n"
        "{brief: ≤120 字的一句话方向（必须含'我方 vs 最强邻国'的国力对比判断与获胜路径），"
        "focus: [最多 3 个优先事项]}。\n"
        "依据：下方状态中的【资源台账】【胜利进展】【危险信号】【战略档位】；"
        "愿景服务于获胜条件（领土统治/科技），不写战斗序列细节。\n\n"
        + mechanic_guidance()
    )


def build_turn_system(gear_idx: int | None = None) -> str:
    """Per-turn autonomous decision system (paradigm switch 2026-08-29).

    The agent allocates THIS turn's resources (actions are single-turn;
    reserve discipline comes from the ctx ReservePolicy line).
    """
    gear_part = ""
    if gear_idx and gear_idx in GEAR_POLICY:
        gear_part = gear_policy(gear_idx) + "\n"
    return (
        "直接输出JSON（{actions:[...], brief:\"...\"}），禁止任何思考过程或解释。"
        "你是《文明时代2》的决策者：围绕当前最重要的事分配**本回合**资源"
        "（行动点/金/外交点/科技点）；数量由局面决定，焦点优先，无数量预置。\n"
        "和谈回应：若【待处决策消息】含对方求和/和约（WeCanSignPeace/PeaceTreaty）——"
        "愿意停战→输出 peace_treaty{交战方}（引擎发起停战）；不愿→按正常打。"
        "兵力/金库/战争分任一明显不利且无胜算 → 也输出 peace_treaty 止损。\n"
        + gear_part
        + actions_prompt_spec()
    )


def plan_turn_closing(cur: int) -> str:
    return (f"\n当前回合 {cur}。请一次性规划未来 10 回合（当前回合算第 1 回合）；"
            "brief 必须写明我方 vs 最强邻国的国力对比判断。")


def war_turn_closing() -> str:
    return ("\n【战争状态】当前正与邻国交战。请给出下一回合的战争操作（数量不限），重点："
            "推进军队到前线、征募新兵、必要时和谈；僵局判定：最后交火>39/49+回合无占领/"
            "战争>299 → peace_treaty 止损。")


GOLD_SAFE = 500


def budget_guard(ledger: dict) -> str:
    """T015-followup: gold-floor guard (gold<GOLD_SAFE or negative net income).

    The engine correctly rejects invest/invest_dev when money<0 (precondition
    nMoney>0), so repeated failed sends waste actions (and prompt LLM turns);
    better to forbid gold actions outright while the coffer is low.
    """
    try:
        gold = int(ledger.get("gold") or 0)
    except (TypeError, ValueError):
        return ""
    inc = ledger.get("income") or {}
    gold_net = inc.get("gold")
    net_neg = isinstance(gold_net, (int, float)) and gold_net < 0
    if gold < GOLD_SAFE or net_neg:
        net_s = f"{gold_net}/回合" if gold_net is not None else "?"
        return (f"【金库提示】金库 {gold}（净收益 {net_s}）：金币类动作（invest/invest_dev/"
                "send_gift/support_rebels/construct/move_capital）单价见资源速查，"
                "低金库时其收益打折——请自行权衡取舍（不禁止；军事移动/科技点不受影响）。"
                f"另：金库<{GOLD_SAFE} 底线时征兵动作会被规则拒绝（引擎 0.5K 同款）——"
                "请改用现有部队调动/进攻，不要重复发征兵（会被丢弃）。")
    return ""
