# Feature Specification: AoC2 AI Player

**Feature Branch**: `001-aoc2-ai-player`

**Created**: 2026-08-29

**Status**: Baseline (`converge` 重建：以 2026-08-23 会话 + 现有代码为事实源回写)

**Input**: 会话 b8bbafe2（2026-08-23，用户全部拍板）+ 代码现状（v40 桥）+ 审视报告（2026-08-29）

## Clarifications

### Session 2026-08-29

- Q: 定位调整——Agent 替代玩家进行游戏，玩家通过游戏外的数据化看板实时了解 Agent 的决策、操纵国家状态，是否采纳? → A: 采纳。Agent 为唯一玩家（退出"独立玩家 + 旁观"模式），用户主界面 = 游戏外数据化看板。
- Q: 决策范式：取消"一次调用决定未来 10 回合动作"，改为 Agent 自主决策——批量计划重新定位为何种形态? → A: Option B——计划降级为"10 回合战略愿景"（仅文字目标，无回合动作），每回合由 Agent 自主决策（单回合资源分配 + 取舍）；愿景每 10 回合或重大变化（领土损失/战略变更/关键事件）时重生成。
- Q: 储备纪律（金/兵力缓冲应对敌方突袭）的定量口径? → A: 动态——金储备下限 = 3 × 每回合净收入（无固定数值）；军队储备 = 威胁分级动态线（1.2× 提示 / 1.5× 强制重规划，可测）。
- Q: 每回合 LLM 调用成本（原批量计划 10 回合 1 次 vs 每回合 1 次）如何取舍? → A: Option C——每 2 回合一次常规决策 + 关键事件触发（领土损失/战争状态转变/新决策消息/战略变化/愿景到期），维持成本与自决平衡；决策上下文必须**简短准确**（杜绝长篇大论：关键信息优先、无重复、单次语境精炼）。
- Q: 引擎直调层是否迁移到源码级桥（EngineGateway 打入游戏 classpath），现 ASM javaagent 版如何处置? → A: 全量切换，本回归内移除 ASM javaagent（Option A）。动作空间 = 玩家等价动作 + 全量信息查询，禁止数值直改（setMoney/setResources/setTurn 等作弊调试类）。
- Q: 新定位下，用户指挥 Agent 的主入口放哪里，游戏内 HUD 与热键如何处置? → A: 指挥全部移至 dashboard（文本战略/六档/暂停/计划面板控件）；游戏内 HUD 只读 + 上帝视角保留，热键（Insert/PageUp/PageDown/END）移除（Option A）。
- Q: 和谈契约缺口如何关闭（FR-014）? → A: 超出和谈——以"玩家等价动作全集"关闭：对局内玩家可执行的所有操作（军事/外交/内政/经济/科技/建造/视图）均须经 API 直接调用（含 peace_treaty）；以引擎源码枚举为唯一事实源，ACTION_SPEC 覆盖率 100%。
- Q: 玩家战略心得框架是否纳入? → A: 采纳为决策模型（FR-017）：操作按成本五分类（查询/金币/行动力/外交点数/多资源）；每回合以有限收入（金/行动力/外交点）配置最大化收益；决策前先读资源存量+每回合收入，再快速评估邻国（人口/经济/领土）；核心战术 baseline = 渔翁得利（挑动两强开战、胜者"同化"期突袭）；获胜条件机制以源码验证后固化。

## 用户场景与测试（mandatory）

> 现状说明：核心能力已在 v9-v40 真机验证。各 Story 的"独立测试"即真机验收路径；
> 每项标注 [已实现] / [部分] / [缺失] 的落地状态。

### 用户故事 1 - Agent 替代玩家的无人值守游戏（Priority: P1）[已实现]

用户开启一局游戏后，Agent 替代玩家操纵该国逐回合游玩（Agent 国 = 唯一玩家控制国，内置 AI
自动跳过），无需用户值守；用户通过游戏外数据化看板（dashboard）实时了解 Agent 的决策、操作
与国家状态。Agent 的每次决策、执行回执、回合推进全程记录，不占用户鼠标键盘；游戏画面保留
上帝视角（无迷雾）供用户随时瞥见。

**Why this priority**: 项目的存在意义；其余全部故事都依附于这条链。

**独立测试**: 开启一局 → `agent\panel.py` 启动 Agent → 观察连续 5+ 回合决策→执行→endTurn→推进、
sessions/ 出现完整 turns.jsonl；dashboard 显示每回合决策流/国家状态/回执且用户无需值守。

**验收场景**:
1. 给定真实对局已加载，当 Agent 启动，则每回合执行规划动作且桥回执 OK、回合推进
2. 给定双方并行，当用户点击任意省份/文明，则信息弹窗正常弹出且不被 Agent 回合打断
3. 给定 Agent 运行，当打开 dashboard，则决策流/国家状态/回执以 ≤2s 延迟显示

---

### 用户故事 2 - 看板指挥 + 游戏内只读 HUD（Priority: P1）[部分]

游戏画面内只读显示（保留）：余额、本局/回合 Token（入/出）、最近回合战报（4 行）、当前战略档位；
重启游戏后从磁盘恢复（aoc2_hud.txt）。用户指挥入口在 dashboard：自由文本战略输入、六档战略
选择器、暂停-恢复开关、10 回合计划面板；写 aoc2_strategy.txt / 暂停文件 → Agent 每回合读入
LLM 上下文（机制同旧热键，仅入口迁移）。

**Why this priority**: 2026-08-29 定位调整——用户不值守游戏，指挥入口随主界面（dashboard）迁移；
游戏内 HUD 保留为只读侧栏（成本零、剪辑素材不空窗）。

**独立测试**: 启动 → dashboard 设战略③ → 下一回合 HUD 金色行更新且 LLM 上下文出现战略 →
dashboard 暂停 → Agent 不决策不推进 → 重启游戏 → HUD 数据仍在前次内容。

**验收场景**:
1. 给定 Agent 运行，当在 dashboard 输入"优先吞并西南邻国"提交，则下一回合 Agent 上下文出现
   【用户战略指示】该文本
2. 给定 Agent 运行，当点击 dashboard 暂停，则 Agent 暂停（不决策不推进），再点恢复
3. 给定重启游戏，当桥启动，则 HUD 从 aoc2_hud.txt 恢复上次显示
4. 给定游戏运行，当查看 dashboard 计划面板，则展示当前 10 回合计划（含 brief 与每回合动作）

---

### 用户故事 3 - 批量计划与事件驱动重规划（Priority: P2）[已实现]

一次 LLM 调用规划未来 10 回合并自动逐回合执行；仅"突发事件"触发重新调用（领土损失、
用户战略变化、外交/战争类新消息类型）；周期消息（科技点提醒/未开化/投资完成等）不得触发
重规划；战争期每回合单次调用仅输出下一回合战争操作（含前线兵力对比）。

**Why this priority**: 成本纪律（宪法 III）的形态体现——Token 花在刀刃上。

**独立测试**: 启动无突发事件对局 → 观察 ≥8 回合零 API 调用（logs 无 chat 调用）、turns.jsonl
连续；dashboard 改档 → 下一回合立即 re-plan。

**验收场景**:
1. 给定和平期，当执行计划中无领土损失/消息变化，则 10 回合内仅 1 次 API 调用
2. 给定开战，当回合推进，则每回合恰好 1 次 API 调用且输出战争动作（move_army 限于前线邻接）
3. 给定周期消息到达，当回合执行，则不触发 re-plan

---

### 用户故事 4 - 决策上下文完备（Priority: P2）[已实现]

LLM 上下文包含：日期/回合/国力/省份明细/稳定度（满意度/革命风险/核心省）/邻国国力画像
（省份/军队/人口/金币/科技/关系/首都/边境数/同盟/交战）/外交条约（停战/互不侵犯/防御条约/
保障）/战争列表/前线兵力/条约/8 类技能/科技点/消息类型/战略指示；科技点执行层兜底
（每回合剩余>0 时引擎自动八类目依次分配，不依赖 LLM）。

**Why this priority**: LLM 决策质量的上限由上下文决定，也是剪辑素材的关键数据源。

**独立测试**: 启动 → 检查 HUD/toast "科技点自动投放 N"，turns.jsonl 的 neighbors 含完整画像字段。

**验收场景**:
1. 给定科技点剩余>0，当回合执行完，则引擎自动投放且 skills 各类目增长
2. 给定对局，当 Agent 生成计划，则计划基于邻国国力对比（plan.brief 含相应判断）

---

### 用户故事 5 - 历史持久化与可视化（Priority: P2）[已实现/部分]

每回合结构化落盘（sessions/<date>/turns.jsonl + plan.json）；Dashboard（127.0.0.1:8080）实时
显示状态/Token 曲线/余额/缓存命中/决策历史；`python -m narrator.timeline` 生成单文件 HTML
时间轴。

**Why this priority**: 用户的核心目标之一是"记录每回合数据以便剪辑视频"。

**独立测试**: 运行 3+ 回合 → 浏览器打开 dashboard 核对数据、`python -m narrator.timeline`
生成 timeline.html 包含全部回合。

**验收场景**:
1. 给定 session 数据，当运行 narrator.timeline，则输出时间轴含每回合战报/动作/回执/统计快照
2. 给定 Agent 运行，当打开 dashboard，则余额/Token/缓存命中为最近值（≤30s 延迟）

---

### 用户故事 6 - Agent 生命周期面板与异常防御（Priority: P3）[部分]

`agent\panel.py`：启动/停止/状态（单实例 pid 文件防重；停止按 pid+命令行双匹配杀尽）；
防御：in_game gate（主菜单预览不决策）、自动跳过过渡视图（NextPlayerTurn 确认/TURN_ACTIONS
快进/开始确认/Menu_StartTheGame.done）、消息应答倒序处理、LLM 失败重试与计划校验重试。

**Why this priority**: 生产可靠性；进程堆积同时决策会导致重复操作（已发生两次）。

**独立测试**: `python agent\panel.py` → Start → Status 显示进程/桥/回合 → Stop → 进程全清；
在暂停文件存在时 Agent 不动作。

**验收场景**:
1. 给定 2 个残留 Agent 进程，当使用面板 Stop，则全部被杀且无重复决策
2. 给定主菜单状态，当 Agent 运行，则仅等待不决策（state.in_game false gate）

---

### 边界情形（Edge Cases）

- **主菜单预览对局误判**: 预览实例恒报 turn 1 → 双重判定（in_game=false 且 turn≤1 视为非对局）。
- **自动保存"确认疆域"界面**: NextPlayerTurn 视图由 tick 自动 clickEnd()，不得依赖人工。
- **`newGame` 幂等性** [已知缺陷]: 当前需发两次才切视图，需优化幂等；`bridge_client` 缺 new_game 封装。
- **战争中和谈** [已决议 2026-08-29]: 实现 `peace_treaty`（引擎已有 PeaceTreaty_GameData），
  不删除 prompt 引导；并入 FR-014 玩家等价动作全集统一交付。
- **消息风暴**: Message_TechPoints/Uncivilized/InvestDone 等周期消息白名单化，不得触发 re-plan；
  其余外交/战争消息类型触发。未知类型优先触发（宁可多一次调用，不可漏突发）。
- **LLM 输出不合法**: 重试一次（附"上次输出不合法"提示）；计划校验 parse_plan 严格白名单校验。
- **`_S` 100 回合滑动窗口**: 回合锚定用 `_T`（首都时间线绝对 TURN_ID），`_S` 仅取尾行
  （守卫已实现，勿回退到 `_S` 行数判定）。
- **冷却规则**: 投资/投资发展同省 4 回合窗口；建造 2-3 回合工期；迁都 50 回合锁定；
  引擎层对重复 invest 自动重置窗口重试。
- **战争结束条件**: 无需拖长战争：和谈（若实现）或以停战条约（truce）自然结束；未定论为
  [NEEDS CLARIFICATION]，当前允许以 plan 过期重新规划来恢复和平节奏。

## 需求（mandatory）

### 功能需求

**已实现（含"部分"缺口标注）:**

- **FR-001**: 引擎直调层 = 源码级桥（在反编译源码上仅新增/改写桥接类 EngineGateway + HTTP server，
  `--release 8` 编译随游戏 classpath 加载，HTTP 127.0.0.1）：Agent 动作经 `/action` 队列在 GL 渲染
  线程消费并直调引擎 API。ASM javaagent 版在迁移回归（/state 字段与动作回执与旧桥对拍一致）后
  **本回归内移除**；仅允许新增桥接类，禁止改动引擎核心类（CivData/GameData 等）逻辑。
- **FR-002**: 动作空间（agent/actions.py ACTION_SPEC）必须与引擎 API 一一对应，且**封闭于玩家
  等价动作全集**：对局内玩家的一切可执行操作（军事/外交/内政/经济/科技/建造/视图查询——
  含和谈、停战等未列项，以引擎源码反编译枚举为唯一事实源）均须能以 API 直调。【部分】
  当前已实现 declare_war / recruit_army / move_army / invest / invest_dev / invest_tech(8类) /
  disband_army / move_capital / offer_alliance / construct(7类)；其余由 FR-014 全量补齐，
  每新增动作同步 docs/actions.md。
  **边界（2026-08-29 决议）**: 禁止数值直改（setMoney / setResources / setTurn / 改地图 /
  改文明数据等作弊调试类），导演模式如需作弊视角须单独 allowlist 开关，不进主动作空间。
- **FR-003**: /state 返回：turn/date/turn_state/in_game/money/provinces/units/move_points/tech_points/
  messages/msg_types/skills/my_provinces/province_detail/stability/treaties/wars/front_lines/
  neighbors（含完整画像）/autosave_in。【部分】资源面缺口：外交点数与每回合收入（gold/行动力/外交点
  收入）未暴露——2026-08-29 决议补入 /state（字段名以引擎源码为准，与 FR-017 资源预算输入对接）。
- **FR-004**: 每回合记录 sessions/<date>/turns.jsonl（state/neighbors/decision/brief/results/
  plan_brief/tokens/tokens_cum/balance）与 plan.json；HUD 数据重启恢复。
- **FR-005**: HUD 游戏内渲染于 AoCGame.render 出口（5 行：输入行(仅输入时)/战略行(金)/余额+
  Token(白)/战报×2(灰)），行距 25%，起始 y=62；经 `/hud` 推送→写 aoc2_hud.txt→启动读回。
- **FR-006**: 指挥入口 = dashboard（127.0.0.1:8080 控件）：自由文本战略输入、六档战略选择器、
  暂停-恢复开关、10 回合计划面板；写 aoc2_strategy.txt / 暂停文件 → Agent 每回合读入 LLM 上下文。
  游戏内热键（Insert/PageUp/PageDown/END）已在 2026-08-29 决议中移除。
- **FR-007**: 视图保护：tick 于 hideExtraViews 返回前同帧恢复 visible_*（Rank/History/Wars/
  MilitaryAlliances/WarDetails 等 30+ 项标记先由 updatePlayerData 快照），用户数据窗口零闪断。
- **FR-008**: 战略愿景（2026-08-29 修订，替代动作级批量计划）：1 次调用输出 10 回合**文字愿景**
  （目标/方向，不含回合动作），如"扩张至 60 省/先灭 civ128/保持科技领先"；愿景重生成触发 =
  领土损失 | 战略 sig 变化 | 决策类消息 | 10 回合到期；经 `/plan` 内存通道（dashboard 计划面板仅渲染愿景文本）。
- **FR-009**: 战争分支：任一战（wars 或邻国 war 标志）→ **每回合**单次决策调用（关键事件密集档；
  前线 move_army 邻接约束/征兵补充/和谈止损（由 FR-014 交付）），不投资不建设；决策上下文含
  【资源速查】+【胜利进展】+【前线评分】+【战术建议】——空决策禁止，强制重试后以建议订单保底。
- **FR-010**: 科技点兜底：回合执行完剩余>0 → 引擎层 auto_invest（科研→生产→经济→军费→税收→
  人口→行政→殖民，类别上限内调 1 式探测），toast 通报。
- **FR-011**: LLM provider（agent/llm/）：OpenAI 兼容（DeepSeek 定稿：flash-vision-exp，
  temperature 0.3，max_tokens 8000，thinking disabled，response json）+ 缓存统计 + 余额查询；
  历史 append-only 单行压缩（缓存友好）。
- **FR-012**: Dashboard（narrator/dashboard.py，127.0.0.1:8080）：实时状态/Token 曲线/余额/
  缓存命中/历史决策；timeline.html 生成命令 `python -m narrator.timeline`。
- **FR-013**: 自动推进：NextPlayerTurn 确认点击（tick clickEnd）、TURN_ACTIONS 500ms 节流快进、
  LOAD_* 自动确认、Menu_StartTheGame 初始化完成后自动 done、in_game gate。
- **FR-017**: 战略决策框架（2026-08-29 玩家心得采纳）：
  ① 动作按资源成本五分类——零成本查询 / 金币 / 行动力 / 外交点数 / 多资源；ACTION_SPEC 每动作
  标注成本类型，prompt 明示每回合资源预算（收入 + 存量）；
  ② 决策顺序：先读资源存量与每回合收入 → 评估邻国（人口/经济/领土，结合兵力/科技/关系）→
  配置动作；
  ③ 战术库由 prompt 引导而非硬编码：baseline = 渔翁得利（交易/外交挑动两实力相当国家开战，
  胜者进入"同化"消耗期时对其突袭，小投入换最大领土回报）；攻略战术（社区 + 源码验证）可扩展。
  **分层原则（2026-08-29 用户明确）**: 可执行操作全集 ≠ 游戏机制——操作是原子动作（L1），
  机制是多回合操作序列的复合行为（L2，如"同化"=战争结束后胜者连续回合消耗资源投入、
  "渔翁得利"=挑动→开战→同化窗口→突袭四段式）。Agent 决策模型必须建模 L2：识别机制阶段、
  按触发条件展开多回合操作序列，而非仅枚举 L1 操作。
  ④ 全部决策服务获胜条件（获胜机制见"假设"探索项，源码验证后固化）。
  ⑤ 储备纪律（动态）：金存量下限 = 3 × 每回合净收入（无固定数值，收入为负时下限=
    近 5 回合平均收入 ×3）；决策不得击穿该线——击穿时动作清单必须优先"修复收入/收缩开支"；
    军事线 = 威胁分级动态（1.2× 提示 / 1.5× 强制重规划），宁守备不裸奔。
- **FR-018**: 决策上下文精炼（2026-08-29 用户要求"简短准确，而非长篇大论"）：单次决策包必须
  关键信息优先、无重复信息、无叙事性铺陈；成本速查表与胜利进展行压缩至必要字段；
  历史仅为追加压缩行；禁止把文档全文塞入上下文。

**已知缺陷（须修复才算 SDD 闭合）:**

- **FR-014** [缺口—全量切换主任务]: 玩家等价动作全集未实现。责任清单：① 引擎源码反编译枚举
  全部玩家可执行操作（分类清单）；② 源码级桥 EngineGateway 逐类暴露并真机调通；③ ACTION_SPEC
  覆盖率 100% 并同步 docs/actions.md；④ 已知至少含 peace_treaty（Engine 已有
  PeaceTreaty_GameData；代码核查 2026-08-29：Python ACTION_SPEC 已含 peace_treaty 条目，
  缺口在 Java 桥 `/action` 实现与提示词对应——决议：实现而非删除引导）。
- **FR-015** [缺口]: bridge_client 缺 `new_game()` 封装；AgentBridge newGame 幂等性待优化（v39 报告需发两次）。
- **FR-016** [缺口]: docs/actions.md 与 ACTION_SPEC 不一致（二期表把已实现动作列为未支持）；README 头部残留"模拟本机键鼠输入"旧口径。

### 关键实体

- **BridgeState**: /state JSON 全量（FR-003）；单一事实源；Agent 主循环按 turn_state=INPUT_ORDERS
  且 in_game gate 驱动。
- **Plan**: {brief, turns[{offset,actions,note}], base_provinces, start_turn}；落盘 plan.json。
- **SessionRecord(turns.jsonl)**: 每回合追加行（决策+回执+token+balance+邻国画像）。
- **StrategyFile/HudFile**: 游戏根 aoc2_strategy.txt / aoc2_hud.txt / aoc2_plan.txt —— 桥与 Agent
  间的持久化通道（相对路径 bug 已由 `/plan`,`/hud` 内存通道替代，文件保留为持久化）。

## 成功标准（mandatory）

- **SC-001**: 无突发对局中，10 回合内 LLM 决策调用次数 ≤ 6（= 每 2 回合 1 次常规 + 愿景再生 1 次；
  turns.jsonl 的 tokens 计数佐证）。
- **SC-002**: 开战后每回合 LLM 调用次数 = 1，移动动作（move_army）全部满足"我方省→邻接敌省"。
- **SC-003**: 用户打开的数据窗口跨 ≥3 个回合边界保持可见（无闪断），由截图帧 (PrintWindow) 采样佐证。
- **SC-004**: 战役全程（≥30 回合）无 Agent 进程堆积至 2+（panel Stop 后 Get-Process agent 为 0）。
- **SC-005**: 每次决策输出 token ≤ 1500（thinking disabled + JSON，对比 v8 出 3198 基线）；输入侧
  前缀缓存命中率 ≥ 80%（provider.last_usage 缓存字段）；单次决策上下文输入 ≤ 6000 token（FR-018 精炼可测）。
- **SC-011**: 储备纪律可测：连续 10 回合内，金存量降至 <3× 单回合净收入的回合数 ≤ 2
  （exceeds 时须记录"击穿储备线"事件；turns.jsonl ledger 校验）；军队触发 1.5× 强制线回合内
  必出现重规划或应对动作记录。
- **SC-006**: 游戏崩溃模型：桥以新增桥接类（EngineGateway + HTTP server）随游戏加载，引擎核心类
  禁止修改；真机 ≥5 回合无 ClassNotFound/崩溃为迁移验收基线。
- **SC-007**: README 与 docs/actions.md 描述与 ACTION_SPEC 逐条一致（无"已支持却在未支持表"现象）。
- **SC-008**: 交付基线：spec/plan/tasks 三件套存在且 analyze 无 CRITICAL/HIGH。
- **SC-009**: 动作空间封闭性：以引擎源码枚举的玩家可执行操作全集为基准，ACTION_SPEC 覆盖率
  100%；prompt 引导的每个动作均对应已实现 API（无悬空动作，analyze 该项 0 CRITICAL）。
- **SC-010**: 资源成本标注全覆盖：ACTION_SPEC 每个动作标注成本类型（查询/金币/行动力/外交点数/
  多资源）零遗漏；决策提示词显式包含资源速查（含每动作消耗/门槛）与收入约束（提示词可 grep 验收）。

## 假设

- 游戏为《文明时代2》(Age of Civilizations II) Java/libGDX 原版（含汉化），本机 JDK21 + 游戏内嵌 JRE8。
- 反编译源码（4300+ 类）与分析目录为本机研究资产，不入库。
- 模型端点经 DeepSeek 兼容 OpenAI API；config.yaml（含 API key）不入库，模板为 config.yaml.template。
- 视频合成管线（ffmpeg 变焦影片/字幕烧录，原 M4）本基线不含——视频素材以 turns.jsonl +
  timeline.html 交付，合成脚本留待下一 feature。
- 多语言 README（英文版）为发布阶段工作，本基线不覆盖。
- 获胜条件机制（计分/领土占比/回合目标）与"同化"（assimilation）资源消耗机制：本基线不假定，
  plan 阶段经源码反编译验证后固化到 prompt（宪法 VII 事实优先）；反编译源码为本机研究资产。
