# Implementation Plan: AoC2 AI Player 全量重构（源码级桥 + 机制层）

**Branch**: `001-aoc2-ai-player` | **Date**: 2026-08-29 | **Spec**: [spec.md](./spec.md)

**Input**: /speckit-clarify 2026-08-29 四决议（定位重塑 / 源码级桥全量切换 / dashboard 指挥 / 玩家等价动作全集）+ 用户机制论（操作 ≠ 机制）+ spec.md

**Note**: 本计划不是"基线重建"，而是**架构变更**：从 ASM javaagent 注入桥重构为**源码级 EngineGateway**（直接编译进游戏 classpath 的桥接类），并用**机制层**重塑 Agent 决策模型。现有 v40 链路作为回归基线（其 `/state` 输出与 turns.jsonl 用于迁移对拍）。

## Summary

目标态 = spec.md 全量 FR/SC 达标，核心为三层：

1. **L1 玩家等价动作全集**（源词汇表）：对局内玩家可执行的全部操作 + 全量信息查询，以引擎源码枚举为唯一事实源，禁数值直改（FR-002/FR-014/SC-009）。
2. **L2 机制层**（复合行为，用户 2026-08-29 核心要求）：游戏机制 = 一连串操作叠加的多回合序列（战争→和谈→**同化窗口** → 突袭；投资→收入增长；交涉→关系升温→同盟）。Agent 决策模型必须识别机制阶段、按触发条件展开序列，而非只会单回合点动作。
3. **无人值守面**：dashboard = 指挥（文本战略/六档/暂停/计划面板）+ 监控（决策流/国家状态/资源/余额）主界面；游戏内 HUD 只读 + 上帝视角保留；热键移除（FR-006/宪法 IV.1 修订）。

三条主线缺一不可：**桥（怎么做动作）→ 模型（想什么）→ 界面（用户怎么看/指挥）**。

## Technical Context

**Language/Version**: Python 3.11（agent/dashboard）；Java 8 字节码（`--release 8`，JDK21 编译；游戏内嵌 JRE8 运行）——EngineGateway 与桥接类以 Java 8 为目标，新增类随游戏 classpath 加载

**Primary Dependencies**: requests / pyyaml / watchdog（Python）；JDK8 自带 `com.sun.net.httpserver`（零三方）；CFR 反编译工具（bootstrap 阶段下载至 tools/，研究资产不入库）；无 ASM（本次移除）

**Storage**: sessions/<date>/turns.jsonl + plan.json（不变）；游戏根 aoc2_hud.txt / aoc2_strategy.txt / aoc2_plan.txt（不变，dashboard 改写策略/暂停文件）；DeepSeek API

**Testing**: pytest（actions/parse 纯函数 + mechanics 目录一致性检验——"prompt 引导的机制/动作均已实现"断言）+ 真机冒烟（SC 打卡）+ 迁移对拍（新桥 /state 与旧桥记录字段对比）+ 机制场景验证（quickstart.md）

**Target Platform**: Windows 11 + 本机《文明时代2》Java 版进程。**bootstrap 已完成（2026-08-29）**：
游戏根 = `%USERPROFILE%\Downloads\Age of History II（含汉化）\Age of History II`（`AoC2.exe` 即改名 jar + 自带 `jre\`，`start_game.bat` 参数现成）；反编译源 =
`%USERPROFILE%\Downloads\_aoc2_analysis\decompiled\`（4300+ 类，CFR-0.152 在本目录）；游戏 jar 副本 = `_aoc2_analysis\aoc2.jar`

**Project Type**: 桌面游戏自动化 + 数据管线 + 可视化；dashboard/timeline 为原生 HTML 单文件

**Performance Goals**: 决策调用 <5s（conservative 3.8s 基线）；无突发 10 回合决策调用 ≤6（SC-001 新口径：每 2 回合常规 + 愿景再生 1 次；战争期按 FR-009 每回合）；每次输出 token ≤1500、**决策上下文输入 ≤6000 token**（SC-005 + FR-018 精炼）；dashboard 刷新 ≤2s（US1 验收 3）

**Constraints**: 宪法 VII——机制层每条结论必须源码/真机验证；FR-002 边界——禁数值直改；SC-006——仅新增桥接类、引擎核心类禁止改动；启动参数变更需主面板一键（start_game.bat 扩展）

**Scale/Scope**: 单机单用户；L1 全集以源码枚举为准（预估 20-40 动作）；L2 机制目录初版 ≥10 条（源码验证 + 社区攻略）

## Constitution Check

*GATE: 本计划任何任务不得违反以下原则——违反即驳回重做（宪法 I-VIII）:*

- [x] **I 引擎直调**——EngineGateway 即引擎 API 直调层；无模拟键鼠（比 ASM 更纯粹）
- [x] **II 旁观零冲突**——Agent 不占键鼠；视图保护（FR-007）与上帝视角保留；tick 消费策略不变
- [x] **III 成本纪律**——模型/参数/追加式历史不变；2026-08-29 范式切换后调用节奏按 SC-001 度量化（无突发 10 回合 ≤6 次；输入侧以 FR-018 精炼约束 ≤6000 token，成本与自决平衡经用户明示（clarify C））
- [x] **IV 沉浸式体验**——宪法已按 2026-08-29 决议修订：dashboard 主入口 + HUD 只读；本计划在此范围内设计，无新增违脉
- [x] **V 单实例受控生命周期**——panel 启停、pid 防重、in_game gate 全部保留
- [x] **VI 数据完备**——turns.jsonl 增补：resource ledger（金/行动力/外交点/收入）与机制阶段标注
- [x] **VII 事实优先**——研究阶段先枚举验证，机制目录条目全部带 `[verified] 源码` 标记；未验证条目禁入 prompt
- [x] **VIII 简明**——不做模拟点击类绕路；机制层以"数据目录 + prompt 引导"实现，不引入规划框架/知识表示引擎
- [x] **工程卫生**——config.yaml.template 入库、二进制不入库、推送前 6 类敏感信息审查

## Project Structure

### 文档（本 feature）

```text
specs/001-aoc2-ai-player/
├── spec.md              # 基线规格（已含 2026-08-29 五决议）
├── plan.md              # 本文件
├── research.md          # Phase 0 输出：机制/动作枚举方法与未决研究
├── data-model.md        # Phase 1 输出：实体/状态机（含机制层）
├── quickstart.md        # Phase 1 输出：真机验收指南
├── contracts/           # Phase 1 输出：engine-api.md（桥 REST）+ dashboard-api.md（看板命令）
└── tasks.md             # /speckit-tasks 输出（下一步生成）
```

### 源代码（仓库根，新增/变更面）

```text
game_bridge/engine_gateway/          # 【新增】Java 源码级桥
├── EngineGateway.java               #   引擎 API 直调网关（玩家等价动作 + 查询）
├── BridgeHttpServer.java            #   127.0.0.1 REST（/state /action /plan /hud /command）
├── build.bat                        #   --release 8 编译 → gateway.jar（随游戏 classpath）
└── analysis/                        #   反编译源（CFR 重建，.gitignore）
agent/
├── mechanics/                       # 【新增】机制层
│   ├── catalog.py                   #   机制目录（id/阶段/触发/序列/消耗，[verified] 标记）
│   └── prompts.py                   #   批量计划 & WAR prompt 组装（资源预算 + 机制引导）
├── actions.py                       # ACTION_SPEC 全量扩充 + 成本类型标注（FR-002/SC-010）
├── state.py                         # 资源台账行（金/行动力/外交点/收入）格式化
├── bridge_client.py                 # new_game() 等补封装（FR-015）
├── main.py                          # 循环：机制阶段识别 → 战术选择 → 序列展开
└── panel.py                         # 启停/状态（不变）
narrator/dashboard.py                # 【改】指挥控件 + 决策流/国家状态/资源面板（≤2s 轮询）
docs/
├── actions.md                       # 与 ACTION_SPEC 生成式一致（FR-016）
├── mechanics.md                     # 【新增】机制↔操作对应表（source-verified）
└── README 头部口径                   # 改"引擎 API 直调（源码级桥）"
tests/                               # 【新增】pytest
```

**Structure Decision**: 冻结 agent/game_bridge/recorder/narrator 既有职责边界；新增 `engine_gateway/`（Java 桥，与既有 `agent_bridge/` ASM 版并存直至 ASM 退役）、`agent/mechanics/`、`docs/mechanics.md`、`tests/`。

## Phases

### Phase 0: 研究（产出 research.md）—— ✅ 已完成（2026-08-29 深读）

1. **Bootstrap 事实源**：✅ 游戏根/反编译源/启动方式见 Technical Context；gateway 以 classpath libs 注入（任务 F）。
2. **L1 枚举（源码深读）**：✅ 产出 `docs/mechanics.md` L1 表（含点成本/效果全量，21+ 外交动作、7+1 建筑、投资/同化/殖民公式）。
3. **L2 机制提取**：✅ M-WAR / M-ASSIMILATE（用户"同化窗口"数学成立）/ M-DIPLO-ECON / M-ECON / M-STABILITY / M-TECH / M-WIN / M-TURN 全表 + **AI 指纹 8 战术与机会点**。
4. **未决研究 → 决策**：✅ B/D/C/F 解决（见 research.md 任务表）；E（LLM 兜底）默认语义确定。
5. Decision/Rationale 记录：见 research.md。

### Phase 1: 设计（产出 data-model.md / contracts/ / quickstart.md）

6. 实体与状态机（agent 主循环：认知 → 机制阶段识别 → **愿景(文字) + 逐回合决策** → 执行 → 记录）。
7. EngineGateway REST 契约 + dashboard 命令契约（与 L1 全集双向一致）。
8. quickstart 真机验收路径（含机制场景：同化窗口触发、渔翁得利动作序列、和平条约落地）。
8b. **范式切换设计（2026-08-29 clarify）**：TurnDecision/VisionPlan/ReservePolicy/Cadence 实体
   （见 data-model.md §7）；决策上下文精炼契约（FR-018 关键字段白名单）；SC-011 验收口径。

### Phase 2: 实现（tasks.md 拆解，顺序为依赖序）

9. **桥最小集**：EngineGateway 先搬移现状面（/state /action /tick/front_lines…）+ `peace_treaty` → 真机冒烟（SC-006 基线，≥5 回合无崩溃）。
10. **ASM 退役**：全量切换决议（FR-001）——启动器改用 gateway.jar classpath；旧 agent-bridge.jar 从流程中移除，源码保留作对拍参考。
11. **L1 全集落地**：按 research 枚举逐动作暴露 + ACTION_SPEC/成本标注/docs/actions.md/单测同步（SC-007/009/010）。
12. **L2 机制层**：catalog.py + prompts 重构（资源预算 + 机制阶段引导）+ 机制阶段识别（状态机）；战争结束/同化窗口检测。
13. **/state 扩展**：外交点数 + 每回合收入（FR-003 缺口）。
14. **dashboard 升级**：指挥控件（文本战略/六档/暂停/计划面板）+ 监控面板（决策流/资源/国家状态 ≤2s）。
15. **验证轮**：真机 30 回合 SC-001~010 全量打卡；机制场景过检；analyze 复审核闭合。

## Complexity Tracking

无宪法违反项（见 Constitution Check），无需偏离表。

**已知复杂度点**（可控，不阻塞）：
| 点 | 事实 | 处理 |
|---|---|---|
| 反编译源重建 | CFR 对 4300+ 类有失真风险，但只"新增桥接类" | 重建仅作阅读/签名证据；编译以 javac + aoc2.jar 原字节码为准 |
| 游戏启动 classpath | AoC2.exe 启动方式未核 | Phase 0 bootstrap 期确认（jar 追加 vs libs 目录），两个方案调研 |
| 机制条目工作量大 | 依赖源码细节 | 每条机制独立小任务（研究→验证→入目录），样板先行（war/assimilation/peace） |
| 迁移回归 | 旧桥 ASM 已 v40 稳定 | 以历史 turns.jsonl 为对拍基线；启动器单文件切换可秒回退 |
