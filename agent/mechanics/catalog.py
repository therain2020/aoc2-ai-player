"""L2 mechanics catalog — schema + validators (T027: entries filled, verified=source).

PRINCIPLE (spec FR-017③ 2026-08-29): operations (L1) != mechanics (L2).
A mechanic is a multi-turn behavioural sequence with trigger conditions;
prompt references must land on a VERIFIED entry (constitution VII).
All entries anchored to docs/mechanics.md (line refs in `doc_ref`).
"""
from __future__ import annotations

import re
from typing import Any

VERIFIED_SOURCE = "source"
VERIFIED_SMOKE = "smoke"

#: mid -> {id, verified: ["source"|"smoke"], trigger, phases:[{phase, ops, budget}], exit, doc_ref}
MECHANICS: dict[str, dict[str, Any]] = {
    "war_cycle": {
        "id": "war_cycle",
        "verified": [VERIFIED_SOURCE],
        "trigger": ("宣战窗口：关系 ≤ max(-50, -50/侵略度)、预算>敌×0.695、无 truce、未交战；"
                    "候选排除傀儡/盟/被保证/NAP（AI_Style:315-424）；开战前 3 回合备战"),
        "phases": [
            {"phase": "prepare",
             "ops": ["recruit_army", "move_army", "invest_tech"],
             "budget": "备战 3 回合：前线集结 + 征兵；军费预算>敌×0.695 才打"},
            {"phase": "attack",
             "ops": ["move_army", "recruit_army"],
             "budget": "只攻单省兵力≥10 且我方前线>敌省（贪心判据）；一条主线推进，不打围观"},
            {"phase": "peace",
             "ops": ["peace_treaty"],
             "budget": "僵局阈值：最后交火>39（无战>19）/ 49+ 回合无占领 / 战争>299 → 止损求和"},
        ],
        "exit": "getWarID(civA,civB)==-1 或 getCivsAtWar(a,b)==false；和约后 truce=46",
        "doc_ref": "docs/mechanics.md:71-77,118",
    },
    "internal_stability_gate": {
        "id": "internal_stability_gate",
        "verified": [VERIFIED_SOURCE],
        "trigger": ("lProvincesWithLowStability 非空（稳定<MIN_PROVINCE_STABILITY，正在同化的省被剔除）"
                    "或 省份 rev_max>0.16 —— 先去内后攘外，推迟对外战争"),
        "phases": [
            {"phase": "garrison",
             "ops": ["move_army", "recruit_army"],
             "budget": "驻军拉分：0.65×min((军+0.185×邻军)/(人/15.97),1)；优先补给断供省（2 回合后逐回合恶化）"},
            {"phase": "develop",
             "ops": ["invest", "invest_dev", "construct", "invest_tech"],
             "budget": "低税低产省先投资恢复（行政费+低产出是持续失血）；幸福<0.56 会升风险"},
        ],
        "exit": "低稳定省清零且 rev_max≤0.16（期间不扩张）",
        "doc_ref": "docs/mechanics.md:96-101,118",
    },
    "assimilation_window": {
        "id": "assimilation_window",
        "verified": [VERIFIED_SOURCE],
        "trigger": ("战后新占省 → 低稳定/被夺权者抽血期：稳定<0.62 且风险<0.55 时革命风险起升；"
                    "同化黄金时点 = 胜者被「外交点 6/省 + 大额现金 + N 回合低产出 + 起义风险」拖垮的窗口"),
        "phases": [
            {"phase": "clamp",
             "ops": ["assimilate", "invest", "construct"],
             "budget": "同化前置：外交点≥6 + 钱≥cost 全额 + 每省同时 1 单；同化中省被剔除低稳定列表（省易主/占领即中止）"},
            {"phase": "exploit",
             "ops": ["declare_war", "move_army"],
             "budget": "敌军同化窗口 = 优先打击其低稳定省（引擎 AI 无法产出/抽血缺口）；不吃敌人同化窗口是 Agent 差异点"},
        ],
        "exit": "turnsLeft=0 → Message_AssimilationEnd；省易主或占领中止",
        "doc_ref": "docs/mechanics.md:79-84",
    },
    "diplo_economy": {
        "id": "diplo_economy",
        "verified": [VERIFIED_SOURCE],
        "trigger": ("外交点收入=max(基准+科技+排名+敌人奖励−外交维护费,0)；基准=1+round(10×难度×0.375)；"
                    "上限=85+85×tech/4，硬顶 170；维护费（getCostOfCurrentDiplomaticActions）超过收入时须减持"),
        "phases": [
            {"phase": "ration",
             "ops": ["offer_alliance", "nonaggression_pact", "military_access_give"],
             "budget": "每回合维护费 ≤ 可得收入；点消耗 -20/-8/-4，持续性 -6/-2/-1"},
            {"phase": "spend",
             "ops": ["send_gift", "ultimatum", "support_rebels"],
             "budget": "高耗点动作 -24/-34 需持有对应点是量（ultimatum≥24、support_rebels≥34）且收入可持续"},
        ],
        "exit": "外交点 ≥16 或 无可耗外交动作",
        "doc_ref": "docs/mechanics.md:86-89,51",
    },
    "invest_cycle": {
        "id": "invest_cycle",
        "verified": [VERIFIED_SOURCE],
        "trigger": ("行动点≥12（invest）/≥8（invest_dev）+ 金币>1500 储备 + 每省同时仅 1 个股（4 回合兑付窗口）"),
        "phases": [
            {"phase": "rotate",
             "ops": ["invest", "invest_dev"],
             "budget": "同省间隔≥4 回合，建议各省轮投；经济点=gold/3.5×(0.875+0.125×min(dev×1.75,1))；"
                       "上限=min(eco×0.325,pop×0.265)×(0.65+0.35×dev)×6.75"},
            {"phase": "construct",
             "ops": ["construct"],
             "budget": "Farm/Workshop/Port 提产出；Fort/SupplyCamp 战争期（军费 -0.2）；Library 补科研；"
                       "移动点预付 + gold，每省每类仅 1 座，未完工不可重复建"},
        ],
        "exit": "行动点<8 或 金钱<1500 或 全部省在投",
        "doc_ref": "docs/mechanics.md:28-34,53-63,91-94",
    },
    "stability_revolt": {
        "id": "stability_revolt",
        "verified": [VERIFIED_SOURCE],
        "trigger": ("起义判定：风险>0.16（非首都）且 modRisk=风险×(1+cores/10)−军/人×50 > 0.64×(0.4+0.6×稳定)"
                    "（概率判定→spawnRevolution）；支持叛军会升风险"),
        "phases": [
            {"phase": "shield",
             "ops": ["move_army", "recruit_army", "invest_tech"],
             "budget": "军/人 压制 modRisk 至阈值下；保障补给（断供 10 回合失控）；厌战度战争期上升会压低稳定"},
            {"phase": "recover",
             "ops": ["invest", "invest_dev"],
             "budget": "低稳定拖累全图收益；劳动/税收/货物不足会再降幸福（-0.01225×缺货比）"},
        ],
        "exit": "modRisk≤0.64×(0.4+0.6×稳定) 且风险≤0.16",
        "doc_ref": "docs/mechanics.md:96-101,99-100",
    },
    "tech_science": {
        "id": "tech_science",
        "verified": [VERIFIED_SOURCE],
        "trigger": "tech_points>0；8 类技能上限 25/25/25/25/20/30/30/15，每级得 1 点；升级阈值=幂函（随省数/起始人口/科技）",
        "phases": [
            {"phase": "spending",
             "ops": ["invest_tech"],
             "budget": "阶段投放：战争/备战→military_upkeep、research；和平→taxation、eco_growth、production；"
                       "人口紧张→pop_growth；殖民地→colonization；administration 按需；封顶即换下一类"},
        ],
        "exit": "当回合 tech_points=0 或全部封顶",
        "doc_ref": "docs/mechanics.md:103-104,37",
    },
    "colonization": {
        "id": "colonization",
        "verified": [VERIFIED_SOURCE],
        "trigger": ("外交点≥14 + 行动点≥min(40,16+16×1.6275×距离) + 钱（科技<0.8 惩罚 ×8.25）；"
                    "引擎 AI 排名后 35% 才殖民；殖民锁定：AI 科技不足时 ≥12+rand 回合、cost/budget>22 时 ≥8+rand"),
        "phases": [
            {"phase": "expand",
             "ops": ["colonize", "invest", "recruit_army"],
             "budget": "+5..20 军 + 开发/人口初始值 + iNewColonyBonus=92（人口增速）；殖民新省防御薄弱 → 建 Fort"},
        ],
        "exit": "殖民冷却内 或 外交点<14/行动点不足",
        "doc_ref": "docs/mechanics.md:66,118",
    },
    "win_conditions": {
        "id": "win_conditions",
        "verified": [VERIFIED_SOURCE],
        "trigger": ("判决（每周判）：①领土：己方+附庸+盟友 ≥ PLAYABLE_PROVINCES 或 ≥总×PERC% 或境内文明<2；"
                    "②回合：VICTORY_LIMIT_OF_TURNS≠0 且到达；③科技：任一 ≥VICTORY_TECHNOLOGY（它国即失败）；"
                    "失败=0 省连续 2 回合"),
        "phases": [
            {"phase": "push",
             "ops": ["declare_war", "move_army"],
             "budget": "终局逼近：打掉剩余核心；胜利点（≠胜利条件）仅供和约消耗"},
            {"phase": "survive",
             "ops": ["recruit_army", "move_army"],
             "budget": "守省守都；0 省 2 回合=失败；game_end 信号后过渡视图勿发动作"},
        ],
        "exit": "game_end / Menu_Victory / Menu.eVICTORY|eDEFEAT",
        "doc_ref": "docs/mechanics.md:106-111",
    },
}


def entry(mid: str) -> dict[str, Any] | None:
    return MECHANICS.get(mid)


def is_verified(mid: str) -> bool:
    e = MECHANICS.get(mid)
    return bool(e and isinstance(e.get("verified"), list) and len(e["verified"]) > 0)


def verified_ids() -> set[str]:
    return {m for m in MECHANICS if is_verified(m)}


def assert_verified(mid: str) -> None:
    if not is_verified(mid):
        raise ValueError(f"mechanic not verified (no [source]/[smoke] mark): {mid}")


def refs_in(text: str) -> list[str]:
    """Mechanic ids that appear in a prompt/plan text."""
    found = []
    for mid in MECHANICS:
        if re.search(r"\b" + re.escape(mid) + r"\b", text or ""):
            found.append(mid)
    return found


def invalid_refs_in(text: str) -> list[str]:
    """Referenced-but-unverified mechanics (SC-009 / core guard for tests)."""
    return [m for m in refs_in(text) if not is_verified(m)]
