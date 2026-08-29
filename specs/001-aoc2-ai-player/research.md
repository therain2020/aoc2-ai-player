# Phase 0 Research: AoC2 AI Player（源码深读版，2026-08-29）

> 宪法 VII：所有机制结论 = 反编译源码行号锚定。完整机制表见
> `docs/mechanics.md`（生产事实表）；本文件 = 决策记录 + 未决清单。

## 决策 1：L1 = 玩家等价动作全集（已定稿 + 成本表已出）

**Decision**: 以 `docs/mechanics.md` L1 表为准：军事/战争收尾/内政经济/外交（21 项带点成本）/建筑（7+1）/科技殖民/查询。
**Baseline 修正（深读发现）**：declare_war **不扣外交点**（真实代价=侵略等级+全球关系+军费）；和平条约按**胜利点**自动分配（`AI_UseVictoryPoints`），非"割清单"——Agent 的 peace 动作用 AI 同款构造即可。
**Alternatives**: 菜单类名清单（有漏、有误导，弃）。

## 决策 2：L2 机制层（生产定义+锚定源）

**Decision**: 机制 = 带证据的复合序列，入库 `docs/mechanics.md`（M-WAR / M-ASSIMILATE / M-DIPLO-ECON / M-ECON / M-STABILITY / M-TECH / M-WIN / M-TURN）。
**重心——用户心得已验证**：`M-ASSIMILATE` 完整数学成立：同化=外交点≥6+钱≥cost+N 回合人口转化（`Civilization.runAssimilates`），窗口=胜者陷于"低稳定省（新占领）+6 外交点/省+大额现金+革命风险升（稳定<0.62 且风险<0.55）"的抽血期 → 引擎 AI 宣战候选**不评估对手稳定**（机会实证）。
**Rationale**: 引擎 AI 指纹（8 条战术+每回合序）即"机制合规的最优行为基准线"，Agent prompt 原则与机会点直接对照。

## 决策 3：/state 资源面字段（实现路径已锚定）

- `diplomacy_points` ← `Civ.getDiplomacyPoints()`；收入 ← `Game_Action.getUpdateCivsDiplomacyPoints(int)`（**每回合净增**，含维护费扣除；上限 85+85×tech/4，硬顶 170）
- `move_points` ← 每回合 set 公式（Game_Action:377-391）可直接由桥复算
- `gold.income / gold.expense` ← `Game_NextTurnUpdate.getIncome/getExpenses/getBalance(int)`
- `income` 组以"桥端一次性聚合（每回合 1 次取数）"实现，不逐省复算

## 任务解决表

| 任务 | 状态 | 结论 |
|---|---|---|
| B 胜利条件 | ✅ | `VicotryManager` 静态变量（领土%/回合/科技三选一制）+ `checkGameEnd`；失败=0 省连 2 回合；`gameEnded` 可轮询 |
| C 收入/点字段 | ✅ | 路径见决策 3 |
| D 战争结束信号 | ✅ | `getWarID(civA,civB)==-1` `getCivsAtWar==false`（和约/灭国/停战残留再以 `getCivTruce` 复核） |
| E LLM 连续失败兜底 | 设计默认 | 跳过认知，执行"确定性动作/推进"+ FAIL 标记（保留重试 1 次）；列为实现期 prompt 决策点，默认可接受 |
| F 注入/启动 | ✅ | `jre\bin\javaw.exe -jar AoC2.exe`；Classpath 注入 = gateway.jar 放入游戏目录 classpath/libs 方案，启动器 `start_game.bat` 参数化（游戏根已在 Technical Context 固化） |

## 未决清单（实现期处理，不阻塞）
1. `Ages.json` 实际数值（场景参数）→ SaveDump/真机读数锚定
2. `CFG.dialog_True` 反编译失败区 → 行为推断（不影响主链路）
3. `WAR_SCORE_MODIFIER` 疑似死代码
4. 部落分支语义（AI_Style:246-249）
5. 和约初始胜利点累计路径（`preparePeaceTreatyToSend`）

## 深读产出归档
- `docs/mechanics.md` ← L1 成本表+L2 机制全表+AI 指纹+机会点（Agent 与桥的唯一事实源）
- `data-model.md` ← MechanicsCatalog 实化 + 状态机增强（安内门/预备期）
