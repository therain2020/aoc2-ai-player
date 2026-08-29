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
}

BUILDING_TYPES = ("fort", "farm", "library", "workshop", "armoury", "port", "supply")

TECH_CATEGORIES = (
    "pop_growth", "eco_growth", "taxation", "production",
    "administration", "military_upkeep", "research", "colonization",
)


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


def plan_prompt_spec() -> str:
    return (
        "【批量计划模式】输出 JSON {brief: 总体方针一句话, turns: [10 个元素]}。"
        "每个 turn 元素: {offset: 回合序号(1..10), actions: [动作数组], note: 本回合一句话计划}。\n"
        "动作格式与单回合一致（见可用动作表）。前几回合通常先征兵/投资/投科技点，"
        "中后期再进攻；相邻回合的动作要衔接（如先征兵后进攻需分回合）；"
        "科技点只在第一回合用完（技术效果持续）；所有动作要符合当前的战略档位。\n"
        "决策依据：对比邻国国力（省份/军队/人口/金币/科技）——邻国全面明显落后时是宣战窗口；"
        "关系为敌方已交战时优先保卫；盟友（allied=true）不要进攻。\n"
        "规则（引擎冷却）：①投资invest/investDev 同一省持续4回合窗口，同省间隔≥4回合，建议各省轮投；"
        "②建造construct 完工周期约2-3回合，同一建筑未完工不可重复建，建议分省分建筑轮建；"
        "③征兵recruit_army 每省当回合可批量一次，数量受可征兵上限（人口基数）与行动点约束；"
        "④迁都move_capital 有50回合锁定，只可一次；⑤若金币<1500，只征兵/投科技点，不投资（保留金库）。\n"
        "科技点按当前阶段投放，不机械全倒：战争/备战→military_upkeep、research；和平→taxation、"
        "eco_growth、production；人口紧张→pop_growth；殖民地扩张→colonization；administration按需。"
        "各类封顶：前四类25 政20 军费/科研30 殖民15，封顶后换下一类。"
    )


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
        "peace_treaty{target_civ_id} 向交战方求和(仅战争中使用)\n"
        "动作资源成本: " + " ".join(f"{k}={v}" for k, v in COST_TAGS.items()) + "\n"
        "规则：科技点尽量用完；保留≥1000金币储备；所有动作受【资源台账】预算约束"
        "（金/行动点/外交点存量+每回合收入）；brief=一句话中文战报。输出严格 JSON。"
    )
