# Game Mechanics Inventory（源码验证版，2026-08-29 深读）

> 证据根：`~\Downloads\_aoc2_analysis\decompiled\age\of\civilizations2\jakowski\lukasz\`
> （下称 `SRC/`，相对路径）。全部条目经反编译源码人工核验（宪法 VII）。
> **注意：本构建为深度改版（Game_Ages/瘟疫/意识形态/殖民/FormCiv/VicotryManager 拼写即证），
> 参数可能由 Ages.json 按场景加载——实现期以 SaveDump/真机读数校对。**
> 本文件 = Agent/桥的"机制事实表"；research.md 记录决策与未决。

## L1 操作全集（已验证引擎签名 + 成本）

### 军事
| 操作 | 引擎调用（已验证） | 成本 |
|---|---|---|
| declare_war | `Game.declareWar(int aggressor, int civB, boolean force)` Game.java:9860 | 无点扣（真实代价=侵略等级↑0.025+0.575×省占比 + 世界关系↓ -35 + 军费）。条件：接壤（部落殖民除外）且无 truce、未在交战（Game.java:9844-9871） |
| join_war | `Game.joinWar(int a, int warID)` Game.java:9774 | — |
| recruit_army / move_army / disband | 既有桥面（move 用 `Game_Action.moveArmy…`） | 行动点（move_points 每回合 set 公式见 M-DIPLO-ECON） |
| prepare_for_war | `AI_Style.prepareForWar2` 同款机制（前线集结+征兵，3-6 回合） | → |
| 自动宣战 | 军队进入未宣战敌省 → `Game_Action` 2006-2020 自动 declareWar | — |

### 战争收尾
| 操作 | 引擎调用 | 成本 |
|---|---|---|
| **peace_treaty** | `DiplomacyManager.sendPeaceTreaty(boolean toDefenders, int fromCivID, PeaceTreaty_GameData)` :1427；构造照 `AI_Style:3984-3988`（`PeaceTreaty_Data(iWarID,…)` + `AI_UseVictoryPoints()` 自动分配） | AI 路径 0 直接点耗（入口对外交点无约束——但送过去的是"胜利点"权益） |
| accept / decline | `DiplomacyManager.acceptPeaceTreaty(int,’tag’)` :1450 / `declinePeaceTreaty` :1767 | — |
| 和约自动内容 | `PeaceTreaty_Data.AI_UseVictoryPoints_CivID` :146-267：省打分（己方占 10.0 / 邻接+core 5.0 / 邻接 4.25 / 有core 1.75 / 沿海 0.325 / 其他 0.025）× 距离系数（0.8+0.2×…）；取完转附庸化（:95-144）；胜利点清零 | — |

### 内政/经济
| 操作 | 调用 | 成本/效果 |
|---|---|---|
| invest | `DiplomacyManager.invest(prov, civ, gold)` :270-286 | **行动点≥12**；4 回合兑付 `CivInvest(prov,4,total,pts/turn)`；每省同时仅 1 个股（:716-720）；经济点=`gold/3.5×(0.875+0.125×min(dev×1.75,1))×(0.375+0.625×ageEcoGrowth×10)`；上限 `invest_MaxEconomy_Gold`（min(eco×0.325,pop×0.265)×(0.65+0.35×dev)×6.75） |
| invest_dev | `investDevelopment` :240-256 | **行动点≥8**；4 回合；发育点=`gold/(startPop×1.075)×(0.375+0.625×age×100)`；上限 ≤tech+0.01−dev |
| move_capital | `Game_Action` :3923-3928 | 成本 1+startPop×0.1925+capPop×0.125+(tax+prod)×(2.135+1.866×tech)；**冷却 50 回合法则**（:3916-3921） |
| **assimilate** | `DiplomacyManager.addAssimilate(civ,prov,turns)` :413-419 | **外交点≥6** + 钱≥cost 全额 + 每省同时 1 个；cost=`(265+(税入×0.775+产出×0.237)×(0.665+0.412×dev+0.0825×同化中数)×(1+距首都比)×(1.625−己方民族占比))/10×回合数`；AI 用 10-50 回合（钱≥1.225×cost，回合=min((100−稳定×100)/1.724, 钱/每回合成, 50) AI_Style:3722-3738） |
| festival | `addFestival` :387-397 | 500+总收入×（0.6425+0.1625×tech+0.2×节日数）；7 回合；+幸福 0.0145+0.006×(1−幸福)/回合（邻省+0.0045）；行动点 8 |

### 外交（点成本=菜单标记，实测以 `getCostOfCurrentDiplomaticActions` 为准）
| 操作 | 调用 | 成本 |
|---|---|---|
| offer_alliance | `sendAllianceProposal` :833 | −20；维持 **−6/回合**；关系上限 60-65 |
| nonaggression_pact（互不侵犯） | :1148 | −8；−2/回合；iValue=40 |
| offer_vasalization（附庸化请求） | :1166 | −16；接受→setPuppetOfCivID；附庸缴税（**税入×Vassal_Tribute%** 于 :248-250） |
| military_access ask / give | :1189 / :1216 | −10（需≥10）/ −4；−1/回合；≤40 回合 |
| guarantee_independence | :1232 | −10；−1/回合；≤100 回合（被保证方被宣战→自动参战 Game.java:9918） |
| defensive_pact | :1257 | −10；**−3/回合**；≤40 回合（自动参战 :9914） |
| ultimatum | `sendUltimatum(...,Ultimatum_GameData,int)` :1303-1309 | −24（需≥24）；关系≤−10；接受→truce 30 回合 |
| send_gift | :1274-1280 | −8 + 钱（≤钱×25%） |
| send_insult / decrease_relations | 关系 −30（+0.2/步） | ≤−25 仇恨（阈值 20） |
| trade_request | :1782 | −10 |
| support_rebels | :473-533 | **−34（需≥34）** + 钱；≤35 回合；提升革命风险（×年龄修正+0.2×效率×人口占比×(1.01−幸福)）；每省每回合 cost×(35 档)×1.6275 |
| civilize / form_civilization | CFG.java:2340,2608 | −24（FormCiv 需≥24）；civilize 需≥10 |
| 外交维护费 | `getCostOfCurrentDiplomaticActions` :606-629 | 加总扣外交点收入项 |

### 建筑（成本/效果全表；每省每类仅 1 座；move 点 + gold 预付；build 回合=工期）
| 建筑 | 效果 | 移动点 | 工期 |
|---|---|---|---|
| Fort | 守备 +10/+20，军费 upkeep 60/125 | 12/14 | 2/3 |
| WatchTower | 守备 +4 | 16 | 1 |
| Farm(5级) | 人口增速 +0.05..+0.25 | 14..26 | 1-5 |
| Library(3级) | 科研（每 pop 需求 725→425→225，需支出×stability） | 10/16/20 | 2-4 |
| Workshop(3级) | 产出收入 +0.05/+0.1/+0.15 | 18/24/30 | 2/3/3 |
| Armoury | （科技 0.4 门槛） | 28 | 4 |
| Port | 产出收入 +0.02 | 16 | 1 |
| SupplyCamp | **军费维护 −0.2**（Game_NextTurnUpdate:430） | 14 | 3 |

### 科技/殖民/查询
- `invest_tech(8类)` 技能点（见 M-TECH）；colonize：diplo 点 **14** + 行动点 `min(40,16+16×(1.6275×距离))` + 钱（科技<0.8 惩罚 ×8.25 倍）；+5..20 军、开发/人口初始值、`iNewColonyBonus=92`（人口增速）；殖民锁定：AI 科技不足时 ≥12+rand 回合、cost/budget>22 时 ≥8+rand（AI_Style:717-767）。
- 查询：state/front_lines/neighbors 画像/province_detail/assimilates/`getWarID`/`getCivsAtWar`/`getCivTruce`/`getProvinceValue`（=1+地形+首都2+growth×6+dev×4，Game.java:9105）——零成本。

## L2 机制

### M-WAR 战争循环
宣战门槛（引擎 AI 指纹，AI_Style:315-424）：候选排除傀儡/盟/被保证/NAP/停战；关系 ≤max(−50,−50/侵略度)；得分=预算比+关系×(1+好战度/4)×…；**预算>敌×0.695 打**；0.605 找共同仇恨者联打；否则发 NAP。开战前 3 回合备战。
战斗（`Game_Action` 2554-2814）：攻兵×攻修正 vs 守兵×守修正（守备: 意识形态 DEFENSE%+首都0.15+要塞+地形+科技防御 min(tech×18×1.75,31.5)%+骰子；进攻: 负地形+补给断−min(0.1N,0.85)+科技 min(tech×18,18)%+首都发起+0.1）。胜方伤亡链式、败方全歼；占领→`setCivID`+`updateWarStatistics_ConqueredProvinces`；人口/经济损失入库。
战争分数 = `War_GameData.getWarScore()`（:129-178）：占土百分比换算，±攻守。和约时 AI 按胜利点自动分配（见 L1）。
停战：`getTruce/setTruce`（clamp 0-50，Civilization:1422-1458；每回合 −1，==1 → `Message_Truce_Expired`）；和约 truce=46（45+1）。
战争结束信号（Agent 轮询）: **`Game.getWarID(civA,civB)==-1`**（:7918-7940）或 `getCivsAtWar(a,b)==false`（:10291）。战争赔款：税入 **8%/回合 × 12 回合**（Game_NextTurnUpdate:252-254）。
AI 求和触发（AI.java:105-140）：僵局=最后交火>39（无战>19）/ 49 回合无占领 / 战争>299+国家数 → 向守方发 WE_CAN_SIGN_PEACE。

### M-ASSIMILATE 同化（含突袭窗口，用户心得核心）
1. **前置**：省主权 c+ 未被占领 + **外交点≥6** + 钱≥cost + 每省 1 单（DiplomacyManager:413）。
2. **逐回合转化**（Civilization:656-686）：比例 `(0.00425+(0.04971+rand/10000)×(己方人比)×幸福×min(1−dev/3.75,1))×(1−0.225×(1−稳定)−0.075×革命风险)×0.8`；归民→省人口（:676-678）。
3. **收尾**：turnsLeft=0 → `Message_AssimilationEnd`，省易主/占领即中止（:680-686）。
4. **窗口数学**：战后新占省 → `lProvincesWithLowStability`（稳定<人格 MIN_PROVINCE_STABILITY，正在同化的省被剔除 Province:3687/Game_NextTurnUpdate:95-98）→ 低税低产 + **革命风险起升条件=稳定<0.62 且风险<0.55**（Turn_NewTurn:208-214）→ 起义阈值=风险>0.16 & modRisk>0.64×(0.4+0.6×稳定) 判定（Game_Action:1154-1220）。**窗口=胜者被"外交点 6/省 + 大额现金 + N 回合低产出 + 起义风险"抽血期**——即突袭黄金时点。
5. 引擎 AI 应对：同化打分=pop%×距首%×低稳%（AI_Style:3726），取低稳定省贪心，同化钱按 1.225× cost 预留（:3550-3553）。

### M-DIPLO-ECON 外交经济
- 外交点收入（`Game_Action.updateCivsDiplomacyPoints` :400-428，Turn_NewTurn:121 调用）：`max(基准+科技+排名+敌人奖励−外交维护费,0)`；基准=1+round(10×难度×0.375)；科技=round(10×tech×2.75)；排名=round(10×(1−排名/文明数)×0.775)；敌人=−6+min(6,仇恨数)×6。开局 ×2.65 且 ≥22（:396）。
- 上限：`85+85×tech/4`，超出部分 +1/回合，硬顶 **170**（Civilization:1993-1998）。
- **行动点（move_points）**：每回合 set 而非累加：`6+20×难度×mod+省数×min(tech×1.214,1)×…+20×tech×2.14×…`（Game_Action:377-391）。

### M-ECON 经济引擎（预算最大化主链）
- 回合流转（`Game_NextTurnUpdate` :67-130）：`money += income − expenses`；每省税收入：`pow(就业×税收系数,0.8386)+pow(失业×…,0.7936)` × 年龄修正 × (0.675+0.325×稳定) × 意识形态/幸福×税档系数；产出收入同构。占用省只算行政费。行政费、军费、科研/投资预算份额、通胀（money/(INFLATION_PEAK×1.1275+收入的0.4)×18.13>0.235 触发）、贷款利息 12.74%/月、通胀+贷款→支出。
- 人口增长（Turn_NewTurn:421-428）：增长=pop×(0.2+货物OK?rand/100:0.5)×…×(1+dev/63.3)×GAME_SPEED；农场增速+；拥挤系数≥0.0865。
- 开发增长=÷ageDevMod×devUpdate×min(growth×0.45,0.3705)；占用：−rand/100000。

### M-STABILITY 稳定/幸福/革命
稳定得分（Province:3670-3755）= 人口组分 0.215×min(我方/最大,最大/我方)+1.275×我方占比×(0.725+0.275×幸福) − 革命分 (0.2×风险+0.05×支持叛军) + 核心 0.05 + 占领 (0.45×(0.85+0.2×tech)) + 驻军 0.65×min((军+0.185×邻军)/(人/15.97),1) − 疾病 0.2 → clamp 0.01..1.0。
幸福变化（Turn_NewTurn:465-505）：税收/货物不足（−0.01225×(缺货/最小)×…）/<0.56 升风险（+age×…×(0.56−幸福)/14）。
起义（Game_Action:1154-1220）：风险>0.16（非首都）；modRisk=风险×(1+cores/10)−军/人×50 > 0.64×(0.4+0.6×稳定)→概率判定→新文明 spawnRevolution。
补给断供：省补给 2 回合后逐回合恶化（4%+），10 回合失控（Province:3765-3789）。
厌战度：战争中 +0.00215×min(1.5,时长/(18.37×速度))，和平 −0.00095（:197-204）。

### M-TECH 科研与技能
科研进度=预算×(1+科技修正)+图书馆加成（pop/725/425/225×稳定）；升级阈值=幂函（500+52.45×省+起始pop×0.719×(tech+…)）^(0.746+0.285×tech+…)×tech/均Tech×意识形态系数；tech 0..200 int。技能 8 类（SkillsManager:9-23 上限 25/25/25/25/20/30/30/15，效果：人口+0.75%/点×8、税收+0.2、产出+0.25、行政−0.3、军费−0.35、科研+0.75、殖民−1.0/点）；升级得 1 点/级；引擎 AI 每局随机权重（军费 0.01-0.76）。

### M-WIN 胜利条件（VicotryManager 静态变量制）
- `VICTORY_CONTROL_PROVINCES_PERC=100 / VICTORY_LIMIT_OF_TURNS=0 / VICTORY_TECHNOLOGY=0.0`（VicotryManager:10-14；每场景重置 Game.java:1605）。
- 判决（`Game_Action.checkGameEnd` :2877-2935，Turn_NewTurn:344 每周判）：①领土统治：己方+附庸+盟友 ≥ PLAYABLE_PROVINCES 或 ≥总×PERC% 或境内文明<2;②回合生存：VICTORY_LIMIT_OF_TURNS≠0 且到达→胜利;③科技：任一文明 ≥VICTORY_TECHNOLOGY→我方胜利/它国胜利即失败。
- 失败：0 省连续 2 回合（:2845-2947）；终局 `Menu.eVICTORY/eDEFEAT`（Menu:237）/ `Menu_Victory`；`Game_Action.gameEnded` 静态清零于 Game_NewGame:43/187/325。
- 胜利点（≠胜利条件）：仅和约消耗（`getProvinceValue` 见 L1）。
- 回合历：`Game_Calendar`（TURN_ID/day/month/year；每 age 天数、BC 显示）；回合状态机 `TurnStates{INPUT_ORDERS,LOAD_AI_RTO,TURN_ACTIONS,LOADING_NEXT_TURN,START_NEXT_TURN}`（Game_Action:4035-4040）。

### M-TURN 回合流（Agent 挂载点）
先 `tryToTakeNexTurn`（:103-120）→AI 线程 `Turn_Actions`→`turnMoves`→`startNewTurn`→`Turn_NewTurn`（收入/外交点/裂隙/同化/消息/自动存档 50 回合 `SettingsManager:30`）→`INPUT_ORDERS`。多人局 `Menu_NextPlayerTurn`。RTS 模式仅 1 玩家（RTS:105-107，不可用）。

## AI 指纹（引擎 AI 是机制合规活教材 — 直接抄）
每回合序（AI.java:162-188 + AI_Style:94-188）：响应消息→外交动作(选对手/宣战判断/结盟/组建国家/围剿附庸)→预算管理(税/军费/货物/投资/科研)→低稳定省同化→扩中立→叛军/解体→建筑×1。
8 条顶层战术（证据同上文件）：①先去内后攘外（低稳定≥发生推迟战争:255-261）②只打碾压仗（>0.695 才开战+局部碾压 +单省<10 不打:1820）③预备期 3 回合+前线集结（:4566-4725）④战役集中一路（打最有价值战线）⑤僵局 39/49/299 回合→价值导向和谈⑥同化保全胜果⑦军费纪律战争期不解散（:5235-5239）⑧排名后 35% 才殖民。
**Agent 机会（引擎 AI 做不到的）**：不吃敌人同化窗口（其宣战候选无对手稳定度/补给度判）；无斩首目标（不优先打首都/核心省）；无科技瓶颈规划；每回合仅 1 建筑无联动；宣战时机随机散点；和平期无"战备军力目标"；从不主动求和。

## 附录 未决清单
1. `Ages.json` 实际参数（经济/外交系数）按场景加载——实现期以 SaveDump/真机读数锚定。
2. `CFG.dialog_True`（CFG.java:4440-4461）反编译失败——终局继续对话行为推断（不影响 Agent 主链路）。
3. `War_GameData.WAR_SCORE_MODIFIER(0.7/0.2)` 疑似死代码（:25-26）。
4. 部落/未开化分支（AI_Style:246-249）语义仅推断。
5. 和平条约初始胜利点总额累计路径未全读（`preparePeaceTreatyToSend`）。
