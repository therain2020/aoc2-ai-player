"""Message classification (source-verified, three-kind model per user principle
2026-08-29):

- DECISION : needs agent judgement / carries parameters (war response, treaty
             terms, trade amounts, ultimatum, union, vassalization, ...).
- FIXED    : simple judgement + state change on confirm -> deterministic rule
             flow (e.g. civilize confirm = become civilized; rule-based accept/
             decline when the bridge action lands).
- IGNORE   : notification only, no gameplay effect -> context record only.

Classification source: decompiled Message_*.java list
(analysis dir: <home>/Downloads/_aoc2_analysis/decompiled).
"""
from __future__ import annotations

# decision-class messages (agent LLM answers; never auto-responded)
DECISION_TYPES = {
    "Message_War",                       # 被宣战 -> war branch decides counter-play
    "Message_WeCanSignPeace",            # 和谈提议
    "Message_WeCanSignPeace_StatusQou",  # 白和提议
    "Message_PeaceTreaty",               # 收到和约条款 -> accept or keep fighting
    "Message_TradeReuest",               # 交易请求（带金额）
    "Message_Ultimatum",                 # 最后通牒（吞并/战争抉择）
    "Message_OfferVasalization",         # 附庸化提议
    "Message_CallToArms",                # 号召参战
    "Message_PrepareForWar",             # 备战互动
    "Message_Independence_Ask",          # 附庸独立请求
    "Message_TransferControl",           # 移交控制请求（数值）
    "Message_Union",                     # 合并提议
}

# fixed-rule actions: message -> (action, param template). `params` uses "my_civ"
# as a sentinel resolved against st["my_civ"]. Marked "pending-java" when the
# engine-side accept/decline bridge action is not implemented yet (batch A).
FIXED_RULES = {
    # 开化确认：游牧/可开化体制满足科技门槛后引擎推送（仅玩家文明，带过期回合）。
    # 确认=DiplomacyManager.civilizeCiv(自己)（Menu_InGame_Civilize 同款路径），
    # 失败（门槛未到）静默；消息被 engines 每回合去重刷新 -> 自动重试直到成功确认。
    "Message_Uncivilized": {"action": "civilize", "params": {"target_civ_id": "my_civ"}},
    # ---- 固定规则已定，动作依赖 Java 应答动作组（A 批，落地即启用）----
    # "Message_Gift":             {"action": "accept_gift",     "params": {"target_civ_id": "from_civ"}, "status": "pending-java"},   # 收礼=纯收益 -> 接受
    # "Message_NonAggressionPact":{"action": "accept_nap",      "params": {"target_civ_id": "from_civ"}, "status": "pending-java"},   # 关系>=0 且外交点>=10 -> 接受
    # "Message_DefensivePact":    {"action": "accept_defensive","params": {"target_civ_id": "from_civ"}, "status": "pending-java"},   # 强邻威胁且点>=12 -> 接受
    # "Message_MilitaryAccess_Ask":{"action": "decline_access", "params": {"target_civ_id": "from_civ"}, "status": "pending-java"},   # 默认拒（给=-4点/-1每回合）
}

# everything else is IGNORE (pure notification): periodic tips, construction
# feedback, *_Accepted/*_Denied/*_Expired, relation changes, diseases, etc.
# (relation changes still refresh the resident context — agent.note only).


def classify(mtype: str) -> str:
    if not mtype or mtype == "Message_Type":
        return "ignore"
    if mtype in DECISION_TYPES:
        return "decision"
    if mtype in FIXED_RULES:
        return "fixed"
    return "ignore"


def split_types(msg_types: str) -> list[str]:
    return [t.strip() for t in (msg_types or "").split(",") if t.strip()]


def decision_types(msg_types: str) -> list[str]:
    return [t for t in split_types(msg_types) if classify(t) == "decision"]


def fixed_types(msg_types: str) -> list[str]:
    return [t for t in split_types(msg_types) if classify(t) == "fixed"]


def ignore_types(msg_types: str) -> list[str]:
    return [t for t in split_types(msg_types) if classify(t) == "ignore"]


def resolve_params(template: dict, st: dict) -> dict:
    """Resolve a param template against the state dict ("my_civ" sentinel)."""
    out = {}
    for k, v in template.items():
        if v == "my_civ":
            v = st.get("my_civ")
        out[k] = v
    return out
