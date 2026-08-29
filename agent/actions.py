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


def actions_prompt_spec() -> str:
    """Describe the action space for the LLM system prompt."""
    return (
        "输出 JSON {actions:[...], brief:\"...\"}。动作（每回合 1-3 个）：\n"
        "declare_war{target_civ_id} 宣战 | recruit_army{province_id,count} 征兵 | "
        "move_army{from_province,to_province,count} 移军(须相邻) | "
        "invest{province_id,gold} 金币投资经济 | invest_dev{province_id,gold} 投资发展(需行动点≥8) |\n"
        "invest_tech{category,count} 投科技点,category∈pop_growth/eco_growth/taxation/production/"
        "administration/military_upkeep/research/colonization,count≤tech_points | "
        "disband_army{province_id,count} 解散军队 | move_capital{province_id} 迁都 | "
        "offer_alliance{target_civ_id} 提议结盟 | construct{building_type,province_id} 建造,"
        "building_type∈fort/farm/library/workshop/armoury/port/supply | "
        "peace_treaty{target_civ_id} 向交战方求和(仅战争中使用) |\n"
        "send_gift{target_civ_id,gold} 赠金(扣8外交点+金≤25%库) | send_insult{target_civ_id} 羞辱(扣2,关系大降慎用) |\n"
        "trade_request{target_civ_id,gold} 金买贸易(扣10外交点) | nonaggression_pact{target_civ_id} 互不侵犯40回合(扣8) |\n"
        "offer_vasalization{target_civ_id} 求对方附庸(扣16) | military_access_ask{target_civ_id}/military_access_give{target_civ_id} 军事通行40回合(扣10/4) |\n"
        "improve_relations{target_civ_id} 改善关系(外交点≥5) | decrease_relations{target_civ_id} 恶化关系(扣2,闭馆5回合) |\n"
        "support_rebels{target_civ_id,gold} 扶植叛军(扣34+金,搅乱敌省) | ultimatum{target_civ_id} 通牒吞并傀儡(关系≤−10且24外交点) |\n"
        "civilize{target_civ_id} 开化(≥10外交点) | form_civilization 组建文明(24外交点+1000金) |\n"
        "proclaim_independence{target_civ_id} 独立宣言(扣10) | prepare_for_war{target_civ_id,against_civ_id} 命盟友备战 |\n"
        "call_to_arms{target_civ_id,against_civ_id} 号召盟友参战 |\n"
        "assimilate{province_id,num_of_turns} 同化敌对省(≥6外交点+钱,每省1单,10-50回合) |\n"
        "festival{province_id} 办节日提幸福(8行动点+钱) | colonize{province_id} 殖民荒芜省(≥14外交点+行动点+钱)\n"
        "动作资源成本: " + " ".join(f"{k}={v}" for k, v in COST_TAGS.items()) + "\n"
        "规则：科技点尽量用完；保留≥1000金币储备；所有动作受【资源台账】预算约束"
        "（金/行动点/外交点存量+每回合收入）；brief=一句话中文战报。输出严格 JSON。"
    )
