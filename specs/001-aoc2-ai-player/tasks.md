# Tasks: AoC2 AI Player 全量重构（源码级桥 + 机制层）

**Input**: plan.md（深读版）/ spec.md（2026-08-29 五决议）/ research.md / data-model.md / contracts/ / quickstart.md / docs/mechanics.md

**Prerequisites**: spec.md ✅ | plan.md ✅ | research.md ✅ | data-model.md ✅ | contracts/engine-api.md + dashboard-api.md ✅ | quickstart.md ✅

**Tests**: 按 plan.md Testing 面：pytest 纯函数 + 真机冒烟 + 迁移对拍；具体测试任务见各 Story 与 Polish 阶段。

**Organization**: 按 spec.md 用户故事（US1-US6）分组；每故事独立可实施/可测。

**⚠️ 现状基线（旧"基线重建"已完项，迁移中保留、勿重做）**:
- `agent/actions.py` ACTION_SPEC 已含 `peace_treaty`（仅缺 Java 桥 `/action` 分支）
- `agent/bridge_client.py` 已有 `new_game()/peace_treaty()/push_plan()`；`AgentBridge.newGame` 幂等守卫已写（待真机复验）
- `docs/actions.md` 已重写为权威速查表（11 动作）；README 头部口径已修
- `tests/test_actions.py + test_state.py` 17 passed（2026-08-29）
- 反编译源 = `%USERPROFILE%\Downloads\_aoc2_analysis\decompiled\`；CFR cfr-0.152.jar 同目录

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup（Shared Infrastructure）

**Purpose**: 源码级桥工程骨架与研究工具就位

- [x] T001 建立 `game_bridge/engine_gateway/` 骨架：Java 源目录（包 `agentbridge.gateway`）+ `build.bat`（`--release 8`，javac 输出 `gateway.jar`）+ `README.md`（构建/注入说明）
- [x] T002 [P] `.gitignore` 增补：`game_bridge/engine_gateway/analysis/`、`game_bridge/engine_gateway/build/`、`*.jar` 构建产物；确认 `.bridge/aoc2.jar` 仍不入库
- [x] T003 [P] `tests/` 初始化：`pytest.ini` + `tests/conftest.py`（fixture：aoc2.jar 路径、反编译源根常量、PORT 常量）
- [x] T004 [P] `scripts/rebuild_analysis.py`（从 `_aoc2_analysis/aoc2.jar` 用 CFR 按需刷新 `engine_gateway/analysis/`，产物入 .gitignore；默认读现成反编译源）
- [x] T005 [P] `scripts/api_sig_probe.py`：对 aoc2.jar 批量 `javap` 生成 `tests/expected_signatures.json`（方法签名基线，实现期防漂移）
- [x] T006 依赖与路径盘点写入 `engine_gateway/README.md`：游戏根/jre/AoC2.exe 启动元数据、`start_game.bat` 参数化点

**Checkpoint**: 骨架与研究工具就绪，build.bat 可产出空 gateway.jar

## Phase 2: Foundational（Blocking Prerequisites）

**Purpose**: 源码级桥最小集 + 全量切换——阻断 US1-US6，全部动作面依赖它

- [x] T007 EngineGateway 核心（build OK + 编译/结构复核）：HTTP server 127.0.0.1:7187；`GET /state` 复现旧字段集（EngineApi 反射层——引擎 API 为 protected，源码级桥唯一合规访问路径；旧桥有包内特权、新桥无）；`diplomacy_points/assimilates` 已加（guarded）；income.* 待 T033
- [x] T008 [P] `/action` 迁移：GET管道+POST JSON 双形态（`/action?cmd=…` 兼容旧链路）；引擎调用经 `Gdx.app.postRunnable` 走 GL 线程 + 3-5s latch（禁 ASM → 用 postRunnable 泵替代 render 钩子）；回执 `{result,log,detail}`
- [x] T009 [P] `peace_treaty`：`PeaceTreaty_Data(warID, isAggressor)` + `AI_UseVictoryPoints()` + `DiplomacyManager.sendPeaceTreaty`（旧桥 2 参形态便携）；无战争→FAIL(no war)
- [x] T010 [P] `new_game` 引擎封装：旧桥幂等守卫 + Menu_StartTheGame done 已便携（EngineGateway glTick 含 getInStartGameMenu → clickEnd 路径）
- [x] T011 启动集成（编码，实测定稿 T015）：`GatewayPremain`（引导型 javaagent：无 ASM/无 transformer）为自动启动入口；`build.bat` 产 manifest Premain-Class；`start_game.bat` 三模式：默认 boot-agent / `ENGINE_GATEWAY_CP=1` classpath(无自启,仅调试) / `LEGACY_AGENT=1` 旧 ASM
- [x] T012 [P] `scripts/state_diff.py` 迁移对拍工具（legacy v28/v29_state.json 或 sessions/ jsonl → live /state 字段 diff）
- [x] T013 ASM 退役：归档副本 = `game_bridge/legacy_agent_bridge/`（jar/build.bat/src + README 只读）；原 `agent_bridge/` 冻结；启动流程不再引用（T011 默认模式）
- [x] T014 `agent/bridge_client.py` 适配：DEFAULT_PORT 9110→7187（其余 GET 管道/hud/narration/plan 路径由新桥兼容路由覆盖——T014 全覆盖；真机回归并入 T015）
- [ ] T015 真机冒烟基线（SC-006）：`scripts/run_smoke.py`——起游戏→面板 Start→≥5 回合无 ClassNotFound/崩溃；产 report.md（需游戏窗口，用户在场）

**Checkpoint**: 新桥打通全链路（state→action→endTurn），旧全量切换完成，无 ASM 残留

## Phase 3: User Story 1 - Agent 替代玩家的无人值守游戏（P1）MVP

**Goal**: 用户开一局后 Agent 替代玩家逐回合游玩，无需值守；决策/回执/推进全程记录（游戏画面/键鼠不占）

**Independent Test**: panel Start → 连续 30 回合 决策→执行→endTurn→推进、sessions/ turns.jsonl 完整、dashboard 可见决策流（quickstart §4）

### Implementation for User Story 1

- [x] T016 [US1] `agent/mechanics/catalog.py` 骨架：schema（id/verified/trigger/phases/ops/budget/exit）+ 校验器（is_verified/assert_verified/invalid_refs_in；未 verified 禁入）+ `agent/__init__.py`、包导出
- [x] T017 [US1] [P] `agent/main.py` 机制阶段接线：每回合 `mech_phases.assess(st)`（war_cycle/internal_stability_gate/peace_economy/not_in_game/ended）+ phase/ledger/tactic_ref 注入 war 与 plan 的 ctx 及三处 round 记录（data-model §5/§6）
- [x] T018 [US1] [P] `agent/state.py`：`extract_ledger()` + `ledger_line()`（FR-017① 预算行）并入 `build_turn_context`
- [x] T019 [US1] [P] `agent/actions.py`：COST_TAGS 全 11 动作（含 peace_treaty=diplo）+ `cost_of/untagged`（SC-010 零遗漏守卫，untagged=none）+ prompt 成本行 + 预算约束措辞
- [x] T020 [US1] `agent/panel.py`：BRIDGE 7187 + 新菜单 4) Start game（读 config.yaml game.root → start_game.bat 桥模式启动）
- [x] T021 [US1] 校验脚本 `scripts/verify_turns.py`（字段完整/plan 节奏/警告统计）✅ 代码完成；30 回合无人值守运行=真机冒烟，随 T015 执行

**Checkpoint**: US1 独立可测——30 回合无人值守，turns 完整（MVP 达成）

## Phase 4: User Story 2 - 看板指挥 + 游戏内只读 HUD（P1）

**Goal**: dashboard = 指挥（文本战略/六档/暂停/计划面板）+ 监控（决策流/资源/国家状态 ≤2s）；游戏内 HUD 只读保留、热键移除、重启恢复

**Independent Test**: dashboard 设战略③ → 下回合 HUD 金行更新 + LLM 上下文【战略指示】；暂停/恢复生效；重启游戏 HUD 恢复（quickstart §5）

### Implementation for User Story 2

- [ ] T022 [US2] `narrator/dashboard.py` 指挥控件：POST /api/command（strategy_text/gear/pause → 写 aoc2_strategy.txt + 暂停文件；校验档位 1-6、文本非空）（dashboard-api.md）
- [ ] T023 [US2] [P] `narrator/dashboard.py` 监控面板：GET /api/state TTL 2s（决策流/资源台账/国家状态）+ 前端轮询
- [ ] T024 [US2] [P] 计划面板：GET /api/plan → 10 回合计划 + brief + tactic_ref 渲染
- [x] T025 [US2] FR-006 收尾：`AgentBridge`/新桥侧移除热键处理（Insert/PageUp/PageDown/END 已决议移除）；HUD 只读链路（/hud → aoc2_hud.txt → 启动读回）由新桥保持
- [ ] T026 [US2] US2 独立验证：按 quickstart §5 全项打卡（含 2s 刷新与重启恢复录屏证据）

**Checkpoint**: US1+US2 双就绪——用户次日回来看板即可了解全程并可指挥

## Phase 5: User Story 3 - 批量计划与事件驱动重规划（P2）

**Goal**: 1 次调用规划 10 回合；仅领土损失/战略变化/新消息类型触发重规划；战争期每回合单次 WAR 调用；机制层接入（tactic_ref）

**Independent Test**: 无突发事件 10 回合 ≤1 调用；开战每回合恰好 1 次；周期消息不触发 re-plan（quickstart §3）

### Implementation for User Story 3

- [ ] T027 [US3] `agent/mechanics/catalog.py` 内容填充第一波（verified=source）：internal_stability_gate / war_cycle / assimilation_window / diplo_economy / invest_cycle / stability_revolt / tech_science / colonization / win_conditions（锚定 docs/mechanics.md 行号）
- [ ] T028 [US3] `agent/mechanics/prompts.py` 重构：批量计划 prompt + WAR 分支 prompt——资源预算行（ledger）+ 机制引导（tactic 引用 catalog）+ 成本四原则（FR-017①-③）
- [x] T029 [US3] [P] **两机制消息模型（2026-08-29 用户拍板，已实现）**：`agent/messages.py` 源码级分类表（决策类=宣战/和谈/交易/通牒/协议请求 17 型；其余含 *_Accepted/Denied/Expired 与关系/周期/建成反馈 = 自动）+ `agent/context_store.py` 常驻上下文仓（aoc2_context.json：邻国关系快照同步→下轮决策参考；非邻国/事件→仅持久化）+ main.py 接入（AUTO→respond+同步+零 LLM；DECISION→绝不自动应答、记 ctx、触发再计划）；科技阶段引导入 prompt（战争→军费/科研；和平→税/经/产；封顶即换）
- [ ] T030 [US3] [P] 战争分支升级：M-WAR 参数化（单省≥10 才攻、前线评分、僵局 39/49/299 阈值触发和谈 branch；peace_treaty 由 FR-014 链路承担）
- [ ] T031 [US3] `parse_plan`/校验：tactic_ref ∈ catalog[verified]；legacy 兼容（旧 plan 无 tactic_ref → bag into `no_ref`）
- [ ] T032 [US3] US3 独立验收：≥8 回合零调用 → 开战单次调用 → 周期消息不重规划（数据取自 turns.jsonl tokens/tactic_ref 列）

**Checkpoint**: 成本纪律+机制层化批量计划落地

## Phase 6: User Story 4 - 决策上下文完备（P2）

**Goal**: 上下文含资源面/机制面全量字段（FR-003 缺口闭合 + FR-017①/②输入）；L1 全集封口

**Independent Test**: HUD/toast 科技点投放正常；turns.jsonl 含完整 dict（含 diplom_pts/assimilates/income）；ACTION_SPEC 覆盖率校验 0 CRITICAL

### Implementation for User Story 4

- [x] T033 [US4] /state 资源面扩展（FR-003）：diplomacy_points（`getDiplomacyPoints()`）+ income 组（`getIncome/getExpenses/getBalance` + `getUpdateCivsDiplomacyPoints` 净额）+ assimilates + low_stability_list + truce（`getCivTruce`）+ war_score 双方（`getWarScore`）+ game_end 信号（data-model §1 engine-api.md）
- [x] T034 [US4] L1 外交全集落地（docs/mechanics.md L1 → ACTION_SPEC + EngineGateway）：send_gift / send_insult / trade_request / nonaggression_pact / offer_vasalization / military_access_give|ask / improve_relations / decrease_relations / support_rebels / ultimatum / civilize / form_civilization / proclaim_independence / prepare_for_war / call_to_arms（按 docs/mechanics.md 成本表逐项校验耗点后实现）
- [x] T035 [US4] [P] assimilate / festival / colonize 动作实现（DiplomacyManager.addAssimilate/addFestival/colonize + 前置校验：外交点≥6、钱、移动点、殖民递进（diplo14/行动力/科技惩罚））
- [ ] T036 [US4] [P] 上下文 prompt 组装升级：邻国画像补外交点/同化状态/稳定/战争分数;plan.brief 必须含国力对比判断
- [ ] T037 [US4] 科技点兜底回归（auto_invest 保留；八类顺序与文档同步）
- [ ] T038 [US4] `scripts/action_closure_check.py`：catalog ∪ ACTION_SPEC ∪ 桥实现 ∪ docs/actions.md 四元一致判定（SC-009/SC-010 自检，产报告）

**Checkpoint**: 决策上下文 + 动作空间封闭（3 个 SC 达标收底）

## Phase 7: User Story 5 - 历史持久化与可视化（P2）

**Goal**: turns.jsonl 全量（含 ledger/机制阶段/tactic_ref/战争事件/胜负）+ dashboard 实时 + timeline.html 全回合（US5 验收）

**Independent Test**: 3+ 回合 → timeline.html 含全部回合；dashboard ≤2s 最新（quickstart §4-5 复用采样）

### Implementation for User Story 5

- [ ] T039 [US5] `recorder/`（或 agent/state.py 落盘处）turns.jsonl 字段扩展：ledger + mechanic_phase + tactic_ref + war events + game_end 信号（data-model §6）
- [ ] T040 [US5] [P] `narrator/dashboard.py` 数据流 ≤2s：轮询 + 增量渲染决策流/资源曲线/余额（复用既有 token 面板）
- [ ] T041 [US5] [P] `narrator/timeline.py` 兼容扩展字段（mechanic_phase/tactic_ref 显示卡片）
- [ ] T042 [US5] US5 独立验收（quickstart §4-5/§3 复用）：timeline 完整 + dashboard 最新值断言脚本

**Checkpoint**: 素材链路（用户剪辑目标）全量可出

## Phase 8: User Story 6 - Agent 生命周期面板与异常防御（P3）

**Goal**: 单实例防重、in_game 门、LLM 失败兜底（任务 E 语义）、计划校验重试、暂停语义

**Independent Test**: 残留进程全杀;主菜单不决策;暂停文件存在不动作;LLM 连续失败走 SKIP_TURN（quickstart §4 复用）

### Implementation for User Story 6

- [ ] T043 [US6] LLM 失败兜底实现：重试 1 次（附"上次输出不合法"）→ 失败走 SKIP_TURN（确定性动作/推进 + FAIL 标记记录）→ 连续 3 回合 FAIL 则暂停并 dashboard 告警（taskE 语义，spec Edge Cases）
- [ ] T044 [US6] [P] `agent/panel.py` 防重加固：pid 文件 + pid/命令行双匹配杀尽（既有 + 网关进程一并管）；Start 前 bridge_ready 检查
- [ ] T045 [US6] [P] `agent/main.py` 门强化：主菜单预览双重判定（in_game=false 且 turn≤1）；过渡视图跳过清单确认（NextPlayerTurn/TURN_ACTIONS 快进/LOAD_*/StartTheGame done）
- [ ] T046 [US6] US6 独立验收（quickstart §4）：杀尽/等待/暂停 + 3 连败告警人工复核

**Checkpoint**: 生产可靠性闭环（进程/门/失败三防线）

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: 文档一致性 / 测试面 / 交付申报

- [ ] T047 [P] `docs/actions.md` 按 ACTION_SPEC 生成式全量重写（含成本标签列 + 外交点成本表，FR-016/SC-007 终服）
- [ ] T048 [P] `docs/mechanics.md` ↔ `agent/mechanics/catalog.py` 双向一致性校验脚本 `scripts/mechanics_sync_check.py`
- [ ] T049 [P] `tests/`：test_actions.py（parse/成本标签/冷却提示新增用例）+ test_mechanics_catalog.py（prompt 无未验证引用）+ test_state.py（字段齐全含新增字段）（在既有 17 用例之上扩展）
- [ ] T050 [P] `README.md` 头部口径更新（引擎 API 直调（源码级桥）+ 机制层一句话简介）
- [ ] T051 [P] `docs/pending_fixes.md` 重写（FR-014/015/016 + 任务 B-F 未决清单状态）
- [ ] T052 运行 quickstart.md 全部六段验收，结果归档 `docs/validation.md`（SC-001~010 逐项打卡表）
- [ ] T053 analyze 复审：spec/plan/tasks 三件套一致、无 CRITICAL/HIGH（SC-008），报告归档 `docs/spec-kit-review.md`
- [ ] T054 提交前审查：逐提交 `git log -p` 6 类敏感信息检查；分逻辑提交（宪法附加约束；config.yaml 不入库）

**Checkpoint**: 全量 SC 达标、三件套一致、可提交

## Dependencies & Execution Order

### Phase Dependencies
- Setup（Phase 1）：可直接开始
- Foundational（Phase 2）：依赖 Setup；**未完成前无任何 Story 可开工**
- US1-US6：均依赖 Phase 2；Story 内部按 模型→服务→编排→验收
- Polish：依赖全部 Story

### User Story Dependencies
- **US1 (P1)**: Phase 2 完成后即可开始；T016 catalog 骨架先于 T017 循环
- **US2 (P1)**: Phase 2 后可与 US1 并行（dashboard 依赖桥 /state、/hud 只读链路）；建议 US1 MVP 达成后接续
- **US3 (P2)**: 依赖 US1 主循环（机制阶段在循环内），可并行开发 prompts（T027/T028 独立于 US1 文件）
- **US4 (P2)**: /state 扩展（T033）依赖 T007；L1 全集（T034/T035）独立文件，可与 US3 并行
- **US5 (P2)**: 依赖 US1 记录面（turns.jsonl 字段），dashboard 部分与 US2 共享文件 → 建议 US2 后接续
- **US6 (P3)**: panel 与 US1 共享 main.py/panel.py → 建议最后接续（防御覆盖既有功能）

### Parallel Opportunities
- Phase 1 T002/T003/T004/T005 并行
- Phase 2 T008/T009/T010/T012 并行（不同 Java 类/脚本）
- US1: T018/T019 并行（state.py / actions.py 不同文件）；US2: T023/T024 并行；US3: T029/T030 并行；US4: T034/T035/T036 并行；US5: T040/T041 并行；US6: T044/T045 并行
- Polish: T047-T051 并行

## Parallel Example: User Story 4 并行组

```bash
Task: "L1 外交全集落地 in game_bridge/engine_gateway/ <DiplomacyActions>.java"
Task: "assimilate/festival/colonize in game_bridge/engine_gateway/ <DomesticActions>.java"
Task: "上下文 prompt 组装升级 in agent/mechanics/prompts.py"
```

## Implementation Strategy

### MVP First（US1 = 无人值守可跑）
1. Phase 1 Setup → Phase 2 Foundational（关键：新桥 + 切换，SC-006 冒烟）
2. Phase 3 US1（catalog 骨架 + 主循环 + 30 回合验收）→ **STOP & VALIDATE**（快速出可剪辑素材）
3. 接 US2（用户指挥界面）→ US3/US4 → US5 → US6（防御收尾）

### 风险提示
- 引擎参数随 Age 场景加载：T015 冒烟与 T033 字段以真机读数锚定（research.md 未决 1）
- gateway 注入方式（libs vs -cp）：T011 实测后定稿（两方案均保留）
- 新手桥同源多线程：/action 仅 GL 线程消费（T008），防跨线程竞态（宪法 II/既有边界）

## Notes
- [P] 任务 = 不同文件、无未完成依赖
- Story 标签保证溯源；每 Story 独立可测（依 quickstart 段落）
- T015/T052 需游戏窗口（用户在场）——由用户选时执行
- 提交按 Phase 边界分逻辑 commit（含宪法附加审查）
