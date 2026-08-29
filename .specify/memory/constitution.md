# AoC2 AI Player Constitution

> 本宪法固化 2026-08-23 会话中用户拍板的全部行为准则。
> 任何 spec/plan/tasks 违反以下原则一律 CRITICAL，不得以"便于实现"为由稀释或绕过。

## 核心原则

### I. 引擎直调，绝不模拟人手点击（NON-NEGOTIABLE）
Agent 作为玩家的一切操作必须直接调用游戏引擎 API（经 AgentBridge javaagent 注入 JVM 直调），
**禁止**任何模拟键盘/鼠标输入（pyautogui/SendInput/mouse_event/坐标点击）作为 Agent 执行层。
鼠标和键盘完整保留给旁观者（用户）自由查看地图、省份、弹窗信息。

### II. 旁观者与 Agent 零冲突（NON-NEGOTIABLE）
0. Agent 是独立玩家：Agent 操纵一个国家（内置 AI 对该国自动跳过），用户不是"被代运营"的玩家。
1. 上帝视角：游戏内须关闭战争迷雾（enterGodView 等价机制），用户可看全部文明。
2. 回合推进不得关闭/打断用户打开的任何数据视图（排名/统计/历史/战争/科技等 30+ 项）——
   视图保护（hideExtraViews 同帧恢复）为必须项，禁止"关了再弹回"的闪断方案。
3. Agent 操作与用户点击并行不冲突；Agent 不抢前台，启动不弹窗打扰。
4. Agent 停止时游戏应停留在当前回合等待，不自动乱走（自动推进只发生在 Agent/引擎自身驱动场景）。

### III. 成本纪律（模型与 Token）
1. 决策模型必须使用便宜模型（已定稿：deepseek-v4-flash-vision-exp），禁止默认贵模型（V4PRO 等）。
2. 决策调用参数定稿：temperature 0.3、max_tokens 8000、thinking_disabled（禁止思考消耗 token）、
   response_format JSON（禁止思考混入 content）。
3. 上下文必须缓存友好：历史只追加（append-only）压缩行，不重写；输出强制严格 JSON。
4. 每回合 Token 消耗（入/出）与 DeepSeek 账户余额必须实时可见（游戏内 HUD + dashboard 双通道）。

### IV. 沉浸式游戏内体验
1. 战略指挥输入以 dashboard 为主入口（2026-08-29 修订：替代旧"游戏内热键"条款——原
   Insert/PageUp/PageDown/END 热键已移除，文本战略/六档/暂停/计划看板由 dashboard 控件实现）。
   游戏画面保留只读 HUD 与上帝视角显示，重启后从磁盘恢复。
2. 一切状态反馈（余额/Token/战报/当前战略/计划）以游戏内 HUD + toast 呈现，重启游戏后从磁盘恢复。
3. 完整历史记录（决策/执行回执/Token）持久化于 sessions/，dashboard 与 timeline.html 可随时查看。

### V. 单实例与受控生命周期
1. Agent 由用户通过面板（agent/panel.py）手动启动/停止，禁止堆积多个 Agent 进程同时决策。
2. 游戏/桥/Agent 三者状态以 bridge /state 为单一事实源；Agent 必须在 in_game 确真后才能行动。
3. 回合节奏归 Agent 引擎调用驱动；战争期每回合单次调用、只输出下一回合战争操作。

### VI. 数据完备（剪辑素材优先）
每回合必须落盘：领土变动（_C_n）、全文明统计（_S）、决策、执行回执、Token；历史 HUD/战略
冻结于游戏根目录文本（aoc2_hud.txt / aoc2_strategy.txt / aoc2_plan.txt）供重启恢复。

### VII. 事实优先，源码验证（NON-NEGOTIABLE）
1. 任何关于游戏机制/API 的结论必须先经反编译源码验证或真机实测，禁止凭印象断言
（此前"RTS 2 秒自动推进""原生视图恢复"等错误结论均属违反本条）。
2. 动作空间中的每个动作必须对应真实存在的引擎 API；prompt 引导的动作若引擎未实现即为缺陷。
3. 执行回执以引擎返回为准（OK/FAIL），禁止假设成功。

### VIII. 简明，不做绕路设计
1. 用最直接的链路实现；"模拟点击→截图识别"类间接方案即视为绕路（反面典型，已废弃）。
2. 成本收益不符的注入尝试（如高风险 Game_Render 注入）在 2 次失败后必须降级或改用方案 B（离线改类）。

## 附加约束（工程卫生）

- 凭据（config.yaml）必须被 .gitignore 排除；仅提交 config.yaml.template。
- 游戏二进制/构建产物（.bridge/aoc2.jar、game_bridge/build、agent-bridge.jar 的构建目录）不入库；
  agent-bridge.jar 成品可入库（即开即用）。
- 推送 GitHub 前逐文件审查 diff（内网 IP/凭据/个人信息/内部 URL/配置文件/环境变量名 6 类敏感信息）。

## 开发流程（Quality Gates）

1. 源码验证优先：定位游戏行为 → 反编译源码/引擎 API 签名 → 真机冒烟。
2. 一次性重启原则：攒齐多个桥改动后一次重启验证，避免频繁重启游戏进程。
3. 交付前 check：spec（FR/SC 覆盖）→ plan → tasks 三件套一致；analyze 无 CRITICAL/HIGH 才算就绪。
4. 每次功能落地后同步文档（docs/actions.md 必须与 agent/actions.py ACTION_SPEC 一致）。

## 治理

- 宪法优先于所有其他实践文档；修订需在会话讨论并记录变更，任何单测/实现不得以临时理由绕过。
- spec 中的 FR/SC 必须可测量；不能测量即视为欠规格，需补充或标 [NEEDS CLARIFICATION]。
- 结构变更（移动文件、重命名动作）必须同步更新：actions.md、state.py 提示文本、bridge_client、prompt spec。

**Version**: 1.0 | **Ratified**: 2026-08-29 | **Last Amended**: 2026-08-29
