"""Semantic actions: LLM output validation and bridge execution mapping."""
import json

from agent.mechanics import catalog

ACTION_SPEC = {
    "declare_war": {"target_civ_id": int},
    "recruit_army": {"province_id": int, "count": int},
    "move_army": {"from_province": int, "to_province": int, "count": int},
    "invest": {"province_id": int, "gold": int},
    "invest_dev": {"province_id": int, "gold": int},
    "invest_tech": {"category": str, "count": int},
    "disband_army": {"province_id": int, "count": int},
    "move_capital": {"province_id": int},
    "offer_alliance": {"target_civ_id": int},
    "construct": {"building_type": str, "province_id": int},
    "peace_treaty": {"target_civ_id": int},
    "send_gift": {"target_civ_id": int, "gold": int},
    "send_insult": {"target_civ_id": int},
    "trade_request": {"target_civ_id": int, "gold": int},
    "nonaggression_pact": {"target_civ_id": int},
    "offer_vasalization": {"target_civ_id": int},
    "military_access_ask": {"target_civ_id": int},
    "military_access_give": {"target_civ_id": int},
    "improve_relations": {"target_civ_id": int},
    "decrease_relations": {"target_civ_id": int},
    "support_rebels": {"target_civ_id": int, "gold": int},
    "ultimatum": {"target_civ_id": int},
    "civilize": {"target_civ_id": int},
    "form_civilization": {},
    "proclaim_independence": {"target_civ_id": int},
    "prepare_for_war": {"target_civ_id": int, "against_civ_id": int},
    "call_to_arms": {"target_civ_id": int, "against_civ_id": int},
    "assimilate": {"province_id": int, "num_of_turns": int},
    "festival": {"province_id": int},
    "colonize": {"province_id": int},
    # 交易机制（TradeRequest_GameData / TradeRequest_List 双清单，2026-08-29 源码核实）：
    # 我方给 gold（listLEFT），要求对方 addRight 执行承诺——acceptTradeRequest 中
    # listRight.iDeclarWarOnCivID -> declareWar(对方, 目标)；iFormCoalitionAgainst -> 双方宣战+NAP40+通行40
    "buy_war": {"target_civ_id": int, "declare_war_on": int, "gold": int},
    "coalition_war": {"target_civ_id": int, "coalition_against": int, "gold": int},
    # Budget 面板滑块（玩家等价操作，Menu_InGame_FlagAction_Budget）：
    # 税收/商品/研究/投资 各 0-100；引擎 clamp（税0..1）+支出总和<=200%削减
    "set_budget": {"tax_pct": int, "goods_pct": int, "research_pct": int, "invest_pct": int},
    # 联盟链（2026-08-29 用户机制）：互保条约 / 联合统治提议（引擎 API 核实）
    "guarantee_independence": {"target_civ_id": int},   # 保对方独立（被保方被宣战→我方自动参战）−10 点
    "union_proposal": {"target_civ_id": int},           # 联合统治提议（CFG.createUnion；须同盟基础）−22 点
}

BUILDING_TYPES = ("fort", "farm", "library", "workshop", "armoury", "port", "supply")

TECH_CATEGORIES = (
    "pop_growth", "eco_growth", "taxation", "production",
    "administration", "military_upkeep", "research", "colonization",
)

# docs/mechanics.md M-TECH: per-category skill caps (SkillsManager 25/25/25/25/20/30/30/15)
SKILL_CAPS = {
    "pop_growth": 25, "eco_growth": 25, "taxation": 25, "production": 25,
    "administration": 20, "military_upkeep": 30, "research": 30, "colonization": 15,
}


class ActionError(ValueError):
    pass


# Resource-cost classes (FR-017① / SC-010): query|gold|move|diplo|multi|tech
COST_CLASSES = ("query", "gold", "move", "diplo", "multi", "tech")

COST_TAGS = {
    "declare_war": "multi",   # 真实代价 = 侵略等级↑ + 全球关系↓ + 军费（非点扣，docs/mechanics.md）
    "recruit_army": "move",
    "move_army": "move",
    "invest": "gold",
    "invest_dev": "gold",
    "invest_tech": "tech",
    "disband_army": "move",
    "move_capital": "gold",
    "offer_alliance": "diplo",
    "construct": "multi",     # 金币预付 + 行动点
    "peace_treaty": "diplo",
    "send_gift": "multi",     # 8 外交点 + 金币（引擎削至 25% 金）
    "send_insult": "diplo",   # 2 外交点（闭馆 5 回合，关系 −30 级）
    "trade_request": "diplo", # 10 外交点
    "nonaggression_pact": "diplo",    # 8 外交点/40 回合
    "offer_vasalization": "diplo",    # 16 外交点
    "military_access_ask": "diplo",   # 10 外交点
    "military_access_give": "diplo",  # 4 外交点
    "improve_relations": "diplo",     # 5+ 外交点门
    "decrease_relations": "diplo",    # 2 外交点
    "support_rebels": "multi",        # 34 外交点 + 金币
    "ultimatum": "diplo",             # 24 外交点（关系 ≤−10）
    "civilize": "diplo",              # 10 外交点 + 科技门槛
    "form_civilization": "multi",     # 24 外交点 + 1000 金
    "proclaim_independence": "diplo", # 10 外交点
    "prepare_for_war": "move",        # 备战集结：兵力投入
    "call_to_arms": "diplo",
    "assimilate": "multi",    # 6 外交点 + 同化 cost 金
    "festival": "multi",      # 8 行动点 + festivalCost 金
    "colonize": "multi",      # 14 外交点 + 行动点 + 金（科技<0.8 惩罚 ×8.25）
    "buy_war": "multi",       # 金给目标 + 目标对 declare_war_on 宣战（引擎接受即执行）
    "coalition_war": "multi", # 金 + 双方同时对 coalition_against 宣战 + NAP40 + 通行40
    "set_budget": "query",    # 预算面板整形（无直接资源消耗；影响税收入/支出占比）
    "guarantee_independence": "diplo",   # −10 点（保对方独立，自动参战绑定）
    "union_proposal": "diplo",           # −22 点（联合统治合并，勿轻率：超级大国目标）
}


def cost_of(name: str) -> str | None:
    return COST_TAGS.get(name)


def untagged() -> list[str]:
    """Actions missing a cost tag (SC-010 zero-miss guard)."""
    return [k for k in sorted(ACTION_SPEC) if k not in COST_TAGS]


def parse_actions(raw: str) -> list:
    """Parse LLM JSON body -> list of validated action dicts."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text else text
        text = text.strip()
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ActionError(f"not valid JSON: {e}") from e
    if isinstance(data, dict) and "actions" in data:
        data = data["actions"]
    if not isinstance(data, list):
        raise ActionError("expected a list of actions")
    actions = []
    for item in data:
        if isinstance(item, dict) and "action" not in item and len(item) == 1:
            nested_name, nested_params = next(iter(item.items()))
            if isinstance(nested_params, dict):
                item = {"action": nested_name, **nested_params}
        if not isinstance(item, dict) or "action" not in item:
            continue
        name = item["action"]
        if name not in ACTION_SPEC:
            raise ActionError(f"unknown action: {name}")
        spec = ACTION_SPEC[name]
        params = {}
        for key, typ in spec.items():
            v = item.get(key)
            if not isinstance(v, typ):
                raise ActionError(f"action {name} param {key} must be {typ.__name__}, got {v!r}")
            params[key] = v
        if name == "invest_tech" and params["category"] not in TECH_CATEGORIES:
            raise ActionError(f"invalid tech category: {params['category']}")
        if name == "construct" and params["building_type"] not in BUILDING_TYPES:
            raise ActionError(f"invalid building type: {params['building_type']}")
        actions.append({"action": name, **params})
    return actions


def execute(bridge, actions: list) -> list:
    results = []
    for a in actions:
        name = a["action"]
        method = getattr(bridge, name)
        params = {k: v for k, v in a.items() if k != "action"}
        results.append({"action": name, "params": params, "result": method(**params)})
    return results


def result_ok(res) -> bool:
    """True if an engine receipt reports OK.

    EngineGateway returns a JSON text {"result":"OK"|"FAIL","log":...,"detail":...};
    the legacy bridge returned plain "OK|cmd|..." pipes — both are accepted.
    """
    if isinstance(res, str):
        s = res.strip()
        if s.startswith("{"):
            try:
                return json.loads(s).get("result") == "OK"
            except (json.JSONDecodeError, AttributeError):
                return False
        return s.startswith("OK")
    if isinstance(res, dict):
        return res.get("result") == "OK"
    return str(res).startswith("OK")


def parse_plan(raw: str, max_turns: int = 10) -> dict:
    """Parse batch-plan LLM output: {brief, turns:[{offset, actions:[...]}]}.

    T031: per-turn tactic_ref (if present) must be a VERIFIED mechanic id
    (SC-009); legacy plan without tactic_ref is bagged into the `no_ref` count.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        text = text.strip()
        if text.startswith("json"):
            text = text[4:].strip()
    data = json.loads(text)
    if isinstance(data, list):
        data = {"turns": data}
    if not isinstance(data, dict) or "turns" not in data:
        raise ActionError("plan must contain turns list")
    verified = catalog.verified_ids()
    turns = []
    no_ref = 0
    for t in data["turns"][:max_turns]:
        entry: dict = {
            "offset": int(t.get("offset", len(turns) + 1)),
            "actions": _validate_actions(t.get("actions", [])),
        }
        if t.get("note"):
            entry["note"] = str(t["note"])[:60]
        tac = t.get("tactic_ref")
        if tac:
            if tac not in verified:
                raise ActionError(f"unverified tactic_ref: {tac}")
            entry["tactic_ref"] = tac
        else:
            no_ref += 1
        turns.append(entry)
    if not turns:
        raise ActionError("empty plan")
    return {"brief": str(data.get("brief", ""))[:80], "turns": turns, "no_ref": no_ref}


def _validate_actions(raw_actions: list) -> list:
    actions = []
    for item in raw_actions:
        if isinstance(item, dict) and "action" not in item and len(item) == 1:
            nested_name, nested_params = next(iter(item.items()))
            if isinstance(nested_params, dict):
                item = {"action": nested_name, **nested_params}
        if not isinstance(item, dict) or "action" not in item:
            continue
        name = item["action"]
        if name not in ACTION_SPEC:
            raise ActionError(f"unknown action: {name}")
        spec = ACTION_SPEC[name]
        params = {}
        for key, typ in spec.items():
            v = item.get(key)
            if not isinstance(v, typ):
                raise ActionError(f"action {name} param {key} must be {typ.__name__}")
            params[key] = v
        if name == "invest_tech" and params["category"] not in TECH_CATEGORIES:
            raise ActionError(f"invalid tech category: {params['category']}")
        if name == "construct" and params["building_type"] not in BUILDING_TYPES:
            raise ActionError(f"invalid building type: {params['building_type']}")
        actions.append({"action": name, **params})
    return actions


#: 资源消耗与影响速查（引擎签名核实，docs/mechanics.md L1）——给 LLM 的"经济账"
RESOURCE_ECONOMICS = """【资源消耗速查】（点=外交点；行动点=每回合 set 值；每动作依库内限制取舍）
- declare_war: 无点扣，真实代价=侵略等级↑+全球关系-35+军费升
- recruit_army: 行动点（每省一批扣一次 COST_OF_RECRUIT）+ 金/兵；批量越大越划算
- move_army: 行动点（每支部队）；影响=移动+邻敌触发战斗
- invest: 行动点≥12 + 金 → 省 4 回合经济收益（上限随省经济）
- invest_dev: 行动点≥8 + 金 → 省发展
- invest_tech: 科技点（8 类目，每回合点消耗）
- disband_army: 行动点；move_capital: 金+50 回合冷却
- offer_alliance: -20 点，-6/回合维护；关系上限 60-65
- construct: 行动点(12-30)+金，工期 2-4 回合，每省每类 1 座
- peace_treaty: 和约内容依胜利点自动分配（无点扣）
- send_gift: -8 点 + 金(≤库25%) → 关系↑；send_insult: -2 点 → 关系-30+闭馆
- trade_request: -10 点（金买贸易）；可携带"要求对方对 X 宣战/组反联盟"条款
- nonaggression_pact: -8 点 -2/回；defensive/guarantee: -10 点
- offer_vasalization: -16 点（接受→对方附庸缴税）
- military_access_ask: ≥10 点-10；give: -4 点；40 回合
- support_rebels: ≥34 点 + 金（敌省革命风险）; ultimatum: ≥24 点(关系≤-10)
- civilize: ≥10 点+科技门槛; form_civilization: -24+1000金; proclaim_independence: -10
- assimilate: ≥6 点+金(按省公式)；festival: ≥8 行动点+金(7回合+幸福)
- colonize: 14 点+行动点+金（科技<0.8 惩罚×8.25）
- buy_war: 金（我们的付出）+ 对方承诺对 X 宣战（对方接受即执行）
- coalition_war: 金 + 双方同宣 X + NAP40 + 军事通行40
- set_budget: 预算滑块（税0..1；商品/研究/投资% 四项总和引擎≤200% 削减）
- guarantee_independence: -10 点；对方被宣→自动参战；union_proposal: -22 点（同盟后合并）
"""


def actions_prompt_spec() -> str:
    """Describe the action space for the LLM system prompt."""
    return RESOURCE_ECONOMICS + "\n" + (
        "输出 JSON {actions:[...], brief:\"...\"}。动作数量无人工上限，资源（行动点/金库/外交点/冷却）"
        "即硬上限；数量由局面自然决定——当下最重要的事若是大战役（多省动员、多路进攻）就完整列出该战役"
        "的全部动作，无事可做就给最少必要动作。**没有数量预置**，唯一标准：注意力在优先级最高的目标上，"
        "低优先级让位；禁止凑数，也禁止遗漏紧急事项。\n"
        "declare_war{target_civ_id} 宣战 | recruit_army{province_id,count} 征兵 | "
        "move_army{from_province,to_province,count} 移军(须相邻) | "
        "invest{province_id,gold} 金币投资经济 | invest_dev{province_id,gold} 投资发展(需行动点≥8) |\n"
        "invest_tech{category,count} 投科技点,category∈pop_growth/eco_growth/taxation/production/"
        "administration/military_upkeep/research/colonization,count≤tech_points | "
        "disband_army{province_id,count} 解散军队 | move_capital{province_id} 迁都 | "
        "offer_alliance{target_civ_id} 提议结盟 | construct{building_type,province_id} 建造,"
        "building_type∈fort/farm/library/workshop/armoury/port/supply | "
        "peace_treaty{target_civ_id} 向交战方求和（何时用：战争分≤-20 败势 / 僵局39·49·299回合 / "
        "敌方已求和（收到 Message_WeCanSignPeace / Message_PeaceTreaty）且我方愿意停战 / "
        "金库破产不能再战；执行=发起停战（依胜利点自动分配，对方接受→战争结束，拒绝→继续打）） |\n"
        "send_gift{target_civ_id,gold} 赠金(扣8外交点+金≤25%库) | send_insult{target_civ_id} 羞辱(扣2,关系大降慎用) |\n"
        "trade_request{target_civ_id,gold} 金买贸易(扣10外交点) | nonaggression_pact{target_civ_id} 互不侵犯40回合(扣8) |\n"
        "offer_vasalization{target_civ_id} 求对方附庸(扣16) | military_access_ask{target_civ_id}/military_access_give{target_civ_id} 军事通行40回合(扣10/4) |\n"
        "improve_relations{target_civ_id} 改善关系(外交点≥5) | decrease_relations{target_civ_id} 恶化关系(扣2,闭馆5回合) |\n"
        "support_rebels{target_civ_id,gold} 扶植叛军(扣34+金,搅乱敌省) | ultimatum{target_civ_id} 通牒吞并傀儡(关系≤−10且24外交点) |\n"
        "civilize{target_civ_id} 开化(≥10外交点) | form_civilization 组建文明(24外交点+1000金) |\n"
        "proclaim_independence{target_civ_id} 独立宣言(扣10) | prepare_for_war{target_civ_id,against_civ_id} 命盟友备战 |\n"
        "call_to_arms{target_civ_id,against_civ_id} 号召盟友参战 |\n"
        "buy_war{target_civ_id,declare_war_on,gold} 花钱让 target 对 declare_war_on 宣战（挑拨贸易，引擎强制执行） |\n"
        "coalition_war{target_civ_id,coalition_against,gold} 花钱组成联合阵线：双方对 coalition_against 同时宣战+NAP40+通行40 |\n"
        "guarantee_independence{target_civ_id} 保对方独立 100 回合（对方被宣战→我自动参战；互保=双向各一次） |\n"
        "union_proposal{target_civ_id} 提议联合统治（-22点，同盟后合并=对方全部版图并入统治，扩张不费兵） |\n"
        "military_access_ask{target_civ_id} 求军事通行（-10点）——战争中对盟/邻借路绕后夹击关键省份 |\n"
        "assimilate{province_id,num_of_turns} 同化敌对省(≥6外交点+钱,每省1单,10-50回合) |\n"
        "festival{province_id} 办节日提幸福(8行动点+钱) | colonize{province_id} 殖民荒芜省(≥14外交点+行动点+钱)\n"
        "动作资源成本: " + " ".join(f"{k}={v}" for k, v in COST_TAGS.items()) + "\n"
        "动作数量无人工上限，资源（行动点/金库/外交点/冷却）即硬上限；数量由局面自然决定——"
        "当下最重要的事若是大战役（多省动员、多路进攻）就完整列出该战役全部动作，无事可做就给最少必要动作。"
        "没有数量预置，唯一标准：注意力在优先级最高的目标上，低优先级让位；禁止凑数也禁止遗漏紧急事项。\n"
        "规则：科技点尽量用完；保留≥1000金币储备；所有动作受【资源台账】预算约束"
        "（金/行动点/外交点存量+每回合收入）；brief=一句话中文战报。输出严格 JSON。"
    )
