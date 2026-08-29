"""Gear (六档) -> engine-API execution policy.

2026-08-29 user critique: gear ④ "疯狂扩张" was running as pure recruit-loop —
only one API (recruit_army) used out of 30. Each gear is now mapped to the
specific engine APIs that implement its intent, plus explicit taboos. The text
is injected into the plan prompt (plan_batch_spec(gear_idx)).
"""
from __future__ import annotations

import re

#: canonical six gear labels (kept in sync with dashboard GEARS)
GEAR_TEXT = [
    "①稳扎稳打：优先内政发展，只在极有把握时扩张",
    "②均衡发展：内政与军备并举，伺机扩张",
    "③积极扩张：主动征兵扩军，有优势即开战",
    "④疯狂扩张：全力军事化，持续战争扩张",
    "⑤外交结盟：积极结盟，借力扩张",
    "⑥全面防御：停止扩张，巩固国防与内政",
]

_ORDER = ("invest", "invest_dev", "invest_tech", "construct", "festival",
          "assimilate", "recruit_army", "move_army", "declare_war",
          "support_rebels", "peace_treaty", "offer_alliance",
          "nonaggression_pact", "military_access_give", "call_to_arms",
          "prepare_for_war", "send_gift", "improve_relations", "trade_request")


def _join(names: list[str]) -> str:
    return " / ".join(n for n in _ORDER if n in names)


GEAR_POLICY = {
    1: {
        "focus": "内政优先、边境维稳,只在极有把握时扩张",
        "ops": ["invest", "invest_dev", "invest_tech", "construct", "festival", "assimilate"],
        "diplo": ["nonaggression_pact", "send_gift", "improve_relations"],
        "war": "declare_war 仅 war_cycle 碾压条件：预算>敌×0.695 且 单省我方兵力≥10 且 前线优势",
        "taboo": "无胜算宣战；连续两个计划窗口仅征兵投资（净省 0 且军力<邻国均值时禁止）",
        "pulse": "每 8 回合核查国力排行——邻国全面落后即升级扩张姿态",
    },
    2: {
        "focus": "内政与军备并举,伺机扩张",
        "ops": ["invest", "invest_dev", "invest_tech", "construct", "recruit_army", "move_army"],
        "diplo": ["improve_relations", "send_gift"],
        "war": "邻国直观落后（省/军/人口均<我方×0.8）可 declare_war；否则备战(move_army 集结)",
        "taboo": "打平局战争;同省 4 回合窗口期重复 invest",
        "pulse": "军力达邻国均值×1.1 后进入积极姿态(③)",
    },
    3: {
        "focus": "主动扩军、有优势即开战,攻占后立刻同化收割",
        "ops": ["recruit_army", "move_army", "prepare_for_war", "declare_war", "assimilate"],
        "diplo": ["peace_treaty"],
        "war": "declare_war 目标=全面落后(省/军/人口≤我方×0.77)的邻国;打单点(前线省≥10兵);占省即 assimilate",
        "taboo": "与均势邻居开战;拖 49+ 回合无占领(僵局即 peace_treaty)",
        "pulse": "每 6 回合重估一遍宣战候选;全境占取下打下一家",
    },
    4: {
        "focus": "连续战争节奏:灭弱邻→同化窗口→翻面下一家;渔翁=叛军削强敌+趁敌同化消耗期突袭",
        "ops": ["recruit_army", "move_army", "declare_war", "assimilate",
                "support_rebels", "peace_treaty", "prepare_for_war"],
        "diplo": ["send_gift", "trade_request", "improve_relations"],
        "war": ("连续战争:一轮打小敌(省/军≤我方0.8),打完同化窗口(assimilate 10-20回合)消化完再打下一个;"
                "挑拨(trade):buy_war{target=强邻,declare_war_on=另一强邻,gold=金} 花钱让强者互战,"
                "或 coalition_war 组联合阵线(双方压 one target+NAP40+通行40);"
                "强敌补充=support_rebels(其低稳定省/首都不稳区)削内乱+等同化耗损期再动手;"
                "僵局39/49/299→peace_treaty 止损换下一场"),
        "taboo": "纯征兵无扩张(连续 2 计划净省 0=不合格);单挑碾压级强敌硬碰;同化窗口未消化就再开战",
        "pulse": "每一计划周期必须产出至少 1 场扩张动作;占省数停滞 2 计划→立即复盘转向",
    },
    5: {
        "focus": "联盟链（互保→通行→同盟→联合统治）：以不流血方式吞并强邻版图",
        "ops": ["offer_alliance", "send_gift", "improve_relations", "trade_request",
                "military_access_give", "prepare_for_war", "call_to_arms", "declare_war",
                "guarantee_independence", "union_proposal"],
        "diplo": ["offer_alliance", "send_gift", "improve_relations", "trade_request",
                  "military_access_give", "nonaggression_pact", "guarantee_independence",
                  "military_access_ask", "union_proposal"],
        "war": "先 call_to_arms/prepare_for_war 使其响应(盟友自动入战),再 declare_war 目标；"
               "借力挑拨：buy_war 让盟友打我们小敌/使强邻互斗；coalition_war 合兵围歼目标；无盟不打大仗",
        "taboo": "对盟友宣战;盟友邀请时不响应(call_to_arms 收到须 join_wars? 无动作→防守式响应)",
        "pulse": "联盟链四阶：关系→互保(guarantee_independence 双向=互保条约) → 军事通行(military_access_ask/give 战争借道) "
                 "→ 同盟(offer_alliance) → 联合统治(union_proposal,−22点) —— 超级大国合并=版图+人口翻倍不费兵；"
                 "超级大国技巧：其宣战谁,我方就拉低与谁的关系(decrease_relations),蹭其恨意升关系→同盟→联合统治",
    },
    6: {
        "focus": "全面防御:要塞化+守军+边境稳定+关系止血",
        "ops": ["construct", "recruit_army", "move_army", "festival", "assimilate"],
        "diplo": ["send_gift", "nonaggression_pact", "improve_relations"],
        "war": "不主动宣战;被宣战→war_cycle 防守(defensive 动作集:守备要塞+补给)",
        "taboo": "一切扩张动作(declare_war/assimilate 外省/colonize);大额礼赠超金库25%",
        "pulse": "每 4 回合检查低稳定省/革命风险,清为零再考虑解防",
    },
}


def gear_index(strategy_text: str) -> int | None:
    """Parse ①-⑥ prefix from a strategy file text -> 1..6 or None."""
    if not strategy_text:
        return None
    m = re.search(r"[①②③④⑤⑥]", strategy_text)
    if not m:
        return None
    return "①②③④⑤⑥".index(m.group(0)) + 1


def gear_policy(idx: int) -> str:
    p = GEAR_POLICY[idx]
    return ("【当前档位执行要点】{}。动作主轴: {}；外交/融资: {}；战争: {}；"
            "禁忌: {}；节奏: {}").format(
        p["focus"], _join(p["ops"]), _join(p["diplo"]),
        p["war"], p["taboo"], p["pulse"])
