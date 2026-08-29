# Agent 动作空间（权威速查表）

> 同步源：`agent/actions.py :: ACTION_SPEC`。任何增删动作都必须同步此表
> （宪法：文档-代码逐条一致）。当前动作总数：**30**。

## 全部动作（AgentBridge `/action` 引擎直调）

| 动作 | LLM 参数 | 引擎 API（同包 protected 直调） | 说明/冷却 |
|---|---|---|---|
| `declare_war` | target_civ_id | `CFG.game.declareWar(me, target, false)` | 宣战；开战后 Agent 进入战争专用分支（每回合单次调用） |
| `recruit_army` | province_id, count | `getCiv(me).recruitArmy_AI(province, count)` | 征兵；受人口上限与行动点约束，每省当回合可批量一次 |
| `move_army` | from_province, to_province, count | `gameAction.moveArmy(from, to, count, me, true, false)` | 迁移必须是相邻省；进入敌军省份触发战斗 |
| `invest` | province_id, gold | `DiplomacyManager.invest(province, me, gold)` | 金币投资经济；**同省 4 回合窗口**（重复投资会被拒绝，引擎层自动重置窗口重试一次） |
| `invest_dev` | province_id, gold | 投资发展（Development） | 需行动点 ≥8；冷却同 invest（4 回合窗口） |
| `invest_tech` | category, count | `SkillsManager.add_<类目>(me)` ×count | 8 类目见下；count ≤ tech_points；执行层每回合兜底自动清空剩余点子 |
| `disband_army` | province_id, count | `gameAction.disbandArmy(province, count, me)` | 解散军队 |
| `move_capital` | province_id | `gameAction.moveCapital(me, province)` | 迁都；**50 回合锁定**，只可一次 |
| `offer_alliance` | target_civ_id | `DiplomacyManager.sendAllianceProposal(target, me)` | 提议结盟；对方 AI 自行接受/拒绝 |
| `construct` | building_type, province_id | `constructFort/...` 按类型 | 建造；完工周期约 **2-3 回合**未完工不可重复建，支持类型：fort/farm/library/workshop/armoury/port/supply |
| `peace_treaty` | target_civ_id | `PeaceTreaty_Data(warID,…)` + `AI_UseVictoryPoints()` + `DiplomacyManager.sendPeaceTreaty(...)` | **向交战方求和（仅战争中使用）**：构造 AI 同款停战提议并发送，对方（内置 AI）自动接受/拒绝；无交战返回 `FAIL\|...\|no war` |
| `send_gift` | target_civ_id, gold | `DiplomacyManager.sendGift(target, me, gold)` | 赠金；**−8 外交点**；金额引擎自动削至 ≤25% 金库；对方接受关系↑/拒绝↓ |
| `send_insult` | target_civ_id | `DiplomacyManager.decreaseRelation(me, target, 5)` | 羞辱；**−2 外交点**；关系大幅 ↓（−26~−30 级）+ 双方闭馆 5 回合 |
| `trade_request` | target_civ_id, gold | `TradeRequest_GameData` + `sendTradeRequest(target, me, data)` | 贸易请求（我方金买对方）；**−10 外交点**；对方 AI 自行接受/拒绝 |
| `nonaggression_pact` | target_civ_id | `sendNonAggressionProposal(target, me, 40)` | 互不侵犯 40 回合；**−8 外交点**；−2/回合维护 |
| `offer_vasalization` | target_civ_id | `sendOfferVasalizationProposal(target, me, 16)` | 附庸化请求；**−16 外交点**；接受→对方归属我方（缴税 VASSAL_TRIBUTE%） |
| `military_access_ask` | target_civ_id | `sendMilitaryAccess_AskProposal(target, me, 40)` | 请求军事通行 40 回合；**外交点 ≥10，−10** |
| `military_access_give` | target_civ_id | `sendMilitaryAccess_GiveProposal(target, me, 40)` | 授予军事通行 40 回合；**−4 外交点** |
| `improve_relations` | target_civ_id | `DiplomacyManager.improveRelation(me, target)` | 改善关系；外交点 ≥5（未交战）；按国力/关系加减分 |
| `decrease_relations` | target_civ_id | `DiplomacyManager.decreaseRelation(me, target, 5)` | 恶化关系；**−2 外交点**；关系 ↓ + 闭馆 |
| `support_rebels` | target_civ_id, gold | `supportRebels(me, target, rebelCivID, gold)` | 扶植叛军；**外交点 ≥34，−34 + 金**；rebel_civ_id 缺省自动取候选首个 |
| `ultimatum` | target_civ_id | `Ultimatum_GameData(demandAnexation)` + `sendUltimatum(target, me, data, units)` | 通牒吞并对方（须关系 ≤−10 且其为傀儡）；**−24 外交点**；接受→全境转我 |
| `civilize` | target_civ_id | `DiplomacyManager.civilizeCiv(target)` | 开化部落文明；**−10 外交点** + 科技门槛；接受后该文明换意识形态/国旗 |
| `form_civilization` | （无） | `CFG.formCiv(me)` | 把自己当前属性文明组建为可组建文明；**−24 外交点 + −1000 金**（canFormACiv 检查） |
| `proclaim_independence` | target_civ_id | `sendGuaranteeIndependence_AskProposal(target, me, 40)` | 独立宣言请求；**−10 外交点**；接受→双方互不冲突/保障 |
| `prepare_for_war` | target_civ_id, against_civ_id | `sendPrepareForWar(target, me, against, turns, me)` | 命盟友备战（AI 同款）：集结+征兵 3-6 回合 |
| `call_to_arms` | target_civ_id, against_civ_id | `sendCallToArms(target, me, against)` | 号召盟友参战 |
| `assimilate` | province_id, num_of_turns | `DiplomacyManager.addAssimilate(me, province, turns)` | **同化**：前置己方省/未占领/**外交点 ≥6**/钱 ≥ cost；−6 外交点 + cost 金；每省 1 单，10-50 回合 |
| `festival` | province_id | `DiplomacyManager.addFestival(me, province)` | **节日**：**行动点 ≥8** + 钱 ≥ 500+税产×系数；−8 行动点 + cost 金；7 回合持续 +幸福 |
| `colonize` | province_id | `DiplomacyManager.colonizeWastelandProvince(province, me)` | **殖民**：荒芜省 + 邻接/军队可达；**外交点 ≥14** + 行动点 + 钱；科技 <0.8 惩罚 ×8.25；产出 +5-20 军/初始人口 |

非动作运营命令：`endTurn`(`gameAction.tryToTakeNexTurn()`)、`respondMessages`(removeMessage 倒序)、
`toast`(`CFG.toast.setInView`)、`hud`、`plan`(PageDown 内存通道)、`enterGodView`(`CFG.FOG_OF_WAR=0`)、
`loadGame`/`newGame`(幂等守卫，START 自动 done)。

## 资源成本标签（COST_TAGS，FR-017① 五分类）

> 机械校验源 = `agent/actions.py :: COST_TAGS`（SC-010 零遗漏守卫：
> `tests/test_actions.py::test_cost_tags_zero_miss`）；具体点耗/冷却数值见上文各动作内联说明。

| 分类 | 含义 | 动作 |
|---|---|---|
| `gold` | 金币 | invest / invest_dev / move_capital |
| `move` | 行动点 | recruit_army / move_army / disband_army / prepare_for_war |
| `diplo` | 外交点 | offer_alliance / peace_treaty / send_insult / trade_request / nonaggression_pact / offer_vasalization / military_access_ask / military_access_give / improve_relations / decrease_relations / ultimatum / civilize / form_civilization / proclaim_independence / call_to_arms |
| `multi` | 多资源 | declare_war / construct / send_gift / support_rebels |
| `tech` | 科技点 | invest_tech |
| `query` | 零成本查询 | （Agent 侧不使用，桥 /state 等为单独入口） |

## 科技点 8 类目

pop_growth(人口) / eco_growth(经济) / taxation(税收) / production(生产) / administration(行政) /
military_upkeep(军费) / research(科研) / colonization(殖民)

> 执行层兜底顺序（`main.py _auto_invest_tech`）：research → production → eco_growth →
> military_upkeep → taxation → pop_growth → administration → colonization（类别满即停）。

## LLM 使用规则（写入 prompt 的硬性约束）

1. 科技点尽量用完（每回合 1-3 个动作的优先级中靠前）。
2. 保留 ≥1000 金币储备（<1500 时只征兵/投科技点，不投资）。
3. 投资同省间隔 ≥4 回合，建议各省轮投；建造建议分省分建筑轮建。
4. 战争期：move_army 只从前线我方省 → 相邻敌省；不做投资/建设/结盟。
5. 输出严格 JSON：`{actions:[...], brief:"..."}`（单回合）或
   `{brief:"...", turns:[{offset, actions, note}]}`（批量计划 10 回合）。

## 已知边界

- **和平条约内容**：`peace_treaty` 采用引擎 AI 同款（`PeaceTreaty_Data` 全参与方 + 胜利点自动分配），
  不细粒度控制割地/赔款；如需定制（具体割地/附庸清单）需另立 feature 研究
  `PeaceTreaty_Demands`/`PEACE_TREATY_LIST_OF_DEMANDS` 消息流。
- **外交消息细分应答**（接受/拒绝结盟邀约等）当前统一 `respondMessages` 忽略清单处理；
  战争类消息由 main.py 归类为"突发"触发重规划，周期类（TechPoints/Uncivilized/InvestDone/
  Relations_Increase/ProvincesNotSupplied）白名单化不触发。
