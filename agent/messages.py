"""Message classification (2026-08-29 user decision, source-verified).

TWO-KIND model:
- AUTO  : relationship/periodic/finished-feedback messages -> zero LLM calls.
          Neighbor civs: refresh relation values in the resident context
          (next decision's reference); non-neighbors: persist only.
- DECISION: messages the source code requires the PLAYER to answer (war,
          peace treaty, trade request, ultimatum, pact/alliance/access/
          vassalization/call-to-arms/prepare-for-war/gift/transfer/union
          proposals). These trigger exactly one agent decision and must NOT
          be auto-responded.

Classification source: decompiled Message_*.java list
(analysis dir: <home>/Downloads/_aoc2_analysis/decompiled).
"""
from __future__ import annotations

# message types whose arrival means "the engine is waiting for a player answer"
DECISION_TYPES = {
    "Message_War",                       # 被宣战 -> war branch decides counter-play
    "Message_WeCanSignPeace",            # 和谈提议
    "Message_WeCanSignPeace_StatusQou",  # 白和提议
    "Message_PeaceTreaty",               # 收到和约条款 -> accept or keep fighting
    "Message_TradeReuest",               # 交易请求
    "Message_Ultimatum",                 # 最后通牒
    "Message_NonAggressionPact",         # 互不侵犯提议
    "Message_DefensivePact",             # 防御条约提议
    "Message_MilitaryAccess_Ask",        # 对方申请通行
    "Message_MilitaryAccess_Give",       # 对方给予通行
    "Message_OfferVasalization",         # 附庸化提议
    "Message_CallToArms",                # 号召参战
    "Message_PrepareForWar",             # 备战通知(互动)
    "Message_Independence_Ask",          # 独立请求(影响附庸)
    "Message_Gift",                      # 礼赠请求
    "Message_TransferControl",           # 移交控制请求
    "Message_Union",                     # 合并提议
    # 开化确认（2026-08-29 用户指正）：游牧/可开化体制文明满足科技门槛后，
    # 引擎经 sendUncivilizedMessages 推送（仅玩家文明，MessageBox_GameData 去重更新剩余回合）。
    # 确认=Menu_InGame_Civilize -> DiplomacyManager.civilizeCiv(自己) + 清消息；
    # 消息带过期回合（iNumOfTurnsLeft），不确认则失去开化窗口 —— 必须决策。
    "Message_Uncivilized",
}

# *_Accepted/*_Denied/*_Expired/*_Refused and every feedback/periodic type are
# AUTO by default (treat anything not in DECISION_TYPES as auto)

# legacy whitelisted periodic/feedback types (kept for logging clarity)
AUTO_TYPES = {
    "Message_Relations_Increase",
    "Message_Relations_Increase_Ended",
    "Message_Relations_Friendly",
    "Message_Relations_Insult",
    "Message_TechPoints",
    "Message_InvestDone",
    "Message_InvestDone_Development",
    "Message_ProvincesNotSupplied",
    "Message_AssimilationEnd",
    "Message_Truce",
    "Message_Truce_Expired",
}


def classify(mtype: str) -> str:
    if not mtype or mtype == "Message_Type":
        return "auto"
    return "decision" if mtype in DECISION_TYPES else "auto"


def split_types(msg_types: str) -> list[str]:
    return [t.strip() for t in (msg_types or "").split(",") if t.strip()]


def decision_types(msg_types: str) -> list[str]:
    return [t for t in split_types(msg_types) if classify(t) == "decision"]


def auto_types(msg_types: str) -> list[str]:
    return [t for t in split_types(msg_types) if classify(t) == "auto"]
