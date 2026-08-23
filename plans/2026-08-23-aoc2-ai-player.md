# AoC2 AI Player —— 文明时代2 AI 玩家项目方案

> 日期：2026-08-23 | 状态：草案（待用户审阅）
> 目标：让 LLM Agent 作为《文明时代2》(Age of Civilizations II, Java 版) 的玩家，逐回合决策、模拟输入操作游戏，全程记录每回合数据（领土变动、各项统计、决策、事件），支撑「实时旁观 + 旁白解说 + 视频剪辑素材线」。

---

## 1. 项目背景与需求

- 用户拥有《文明时代2》(Age of Civilizations II) Java 版（含汉化），本地可运行。
- 需求 A：**Agent 作为玩家**——LLM 决策 + 模拟键盘鼠标执行，不修改游戏逻辑（读档/写档仅只读解析）。
- 需求 B：**每回合数据记录**——领土变动、经济人口军事统计、关键决策/事件，形成结构化数据，用于视频剪辑。
- 需求 C：**实时旁观与旁白**——用户旁观 Agent 游玩；旁白（中文解说）以两种形态呈现：
  1. 游戏内提示弹窗（复用 `CFG.toast` 机制）；
  2. 历史旁白时间轴（网页/数据流），供观众回顾局势演化。
- 需求 D：模型可配置——DeepSeek API（OpenAI 兼容）/ 本地 Ollama / 任意 OpenAI 兼容端点。
- 需求 E：项目位于 `D:\GitHub\aoc2-ai-player`，推送至个人 GitHub（`Yemomo511`）。

## 2. 调研事实基础（已验证）

### 2.1 游戏技术栈
- Java 8 + libGDX 引擎（LWJGL3）；`AoC2.exe` 为 Launch4j 启动器，内嵌完整 jar（6744 entry），运行方式等价 `javaw -jar AoC2.exe`。
- 游戏自带 JRE（1.8.0_191）。本机另有 JDK 21（`javac --release 8` 可产 Java 8 字节码）。
- 所有游戏数据/存档均为 **Java 标准对象序列化**（magic `ACED0005`），无加密。

### 2.2 存档体系（源码确认，已实测）
```
<游戏根目录>/saves/games/<MapPath(如 Earth|Asia)>/
├── Age_of_Civilizations          # 存档清单（saveTag; 文本）
├── stats/civ/<civTag>            # 文明全服统计（服务绶带）
└── <saveTag>/                    # saveTag = System.currentTimeMillis()+random
    ├── <saveTag>.json            # 快速信息（小 JSON）
    ├── <saveTag>_1.._11, _2X     # 分模块二进制序列化存档
    ├── TS/
    │   ├── <saveTag>_O           # Timelapse_Owners_GameData：开局省份初始归属
    │   ├── <saveTag>_T           # Timelapse_GameData：各文明首都时间线
    │   ├── <saveTag>_S           # Timelapse_Stats_GameData：每回合全文明统计
    │   └── TURN/
    │       ├── <saveTag>_C_<n>   # Timelapse_TurnChanges：第 n 个保存期的省易主事件
    │       └── Age_of_Civilizations  # 回合保存计数（文本）
```

- 统计结构（`_S`）：`lProvinces/lPopulation/lRank/lTechnologyLevel` = `List<List<Integer>>`（[回合][civID]），`lPlayers_Income/Balance/MilitarySpendings` 同理、（含 HistoryLog）。
- 易主结构（`_C_n`）：`{iProvinceID, iToCivID, isOccupied}` 列表，按保存期归档；`TURNS_BETWEEN_AUTOSAVE`（默认 50，设置 0-100）可调为 1 → 每回合落盘。
- 数据上限：`GRAPH_DATA_LIMIT_*`（省份/人口/玩家数据 100 回合）——Agent 侧自行追加记录，不受限。

### 2.3 UI / 提示系统
- `CFG.toast.setInView(String[,Color])`：游戏底部居中半透明提示条，默认 2s（`setTimeInView` 最长 6s）。已确认源码与注入路径。
- libGDX 布局常量集中在 `CFG`（PADDING/BUTTON_HEIGHT/TEXT_HEIGHT），菜单按钮为规则网格——坐标可由「按钮索引 × 常数」推算，供点击执行器使用。
- 主菜单实测：窗口 1711×1084；主菜单按钮（游戏/编辑器/设置/加载）及二次菜单可被程序化点击导航。

### 2.4 已验证原型（本机）
- `SaveDump.java`（Java8，反射+流字段遍历 → JSON，循环引用 `$refN` 防护）已编译并成功 dump：
  - `game/civilizations/eng`、TS 三件套、`_C_0`、`_S`（本例 Asia 地图即时存档）。
- 模拟点击链路（SetForegroundWindow+SetCursorPos+mouse_event）主菜单点击成功。

## 3. 系统架构

```
┌────────────┐   ┌──────────────┐   ┌───────────────┐   ┌────────────┐   ┌─────────────┐
│ 感知层      │   │ 状态组装      │   │ 决策层         │   │ 执行层      │   │ 记录/旁白层  │
│ game_bridge│ → │ agent/state  │ → │ agent/llm     │ → │ executor   │ → │ recorder*   │
│ SaveDump   │   │ turn 摘要     │   │ provider 抽象  │   │ win32 输入  │   │ narrator    │
│ watchdog   │   │ 历史战况上下文 │   │ 动作→指令 JSON  │   │ 按钮导航    │   │ toast bridge│
└────────────┘   └──────────────┘   └───────────────┘   └────────────┘   └─────────────┘
        ▲                                                         │
        └──────────── 每回合循环（回合结束 → 保存 → 回落盘）─────────┘
```

### 3.1 循环骨架（main.py）
1. 等待/确认游戏主界面 → 定位窗口；
2. 每回合：
   a. 等到新存档落盘（watchdog 见 `TS/` 变化或轮询 `_S` 行数增长）；
   b. `game_bridge` dump `_S` 尾行 + 新 `_C_k` → JSON；
   c. 组装 `TurnContext`（我方统计/相邻文明/敌方值/上回合决策回执/旁白历史）；
   d. LLM 决策 → 结构化指令 `[{action, params}]`（1~5 条）；
   e. `executor` 逐条模拟输入执行（含自查截图）；
   f. agent 侧把决策写入 `jsonl`，回合记录器写全量 `turn_{n}.json`；
   g. 模拟点击「结束回合」→ 回到 a；
3. 异常兜底：执行失败 → 截图 + 状态回读重试（最多 2 次）→ 若仍失败则触发 LLM「恢复再调度」。

### 3.2 动作空间（agent/actions.py）
高语义动作（从反编译源码 `Button_*`、`Game_Action` 提取），第一版先做最重要子集：
- 外交：宣战、和谈、结盟提议、请求通行、要求进贡；
- 建设：投资省份（boost）、修铁路/飞机场（省份 UI）；
- 军事：征募/解散军队、移动军队到省、执行回合内聚合命令（`moveAtWar` 指令）；
- 内政：设置国家政策/贸易路线（后续扩展）；
- 控制：结束回合、打开/关闭菜单。
每个动作 = 动作名 + 参数 + 执行脚本（按钮坐标序列），坐标由「计算+校准截图」得出并存入 `ui_profiles/{resolution}.json`。

### 3.3 LLM Provider（agent/llm/）
- `base.py`：`LLMProvider.choose_action(context) -> list[Action]`，JSON schema 强约束输出；
- `openai_compat.py`：DeepSeek / OpenAI / 任意 `/v1/chat/completions`（`OPENAI_COMPAT_BASE_URL`）；
- `ollama.py`：Ollama `/api/chat`；
- 选择依据 `config.yaml: llm.provider`。
- 成本控制：每回合仅一次主决策调用（300~600 token 上下文），旁白复用同一 provider（`narrator` 可降级模板模式 `narrative.mode: template|llm|hybrid`）。

### 3.4 旁白引擎（recorder/narration.py + narrator/）
四类旁白源（优先级从高到低）：
1. **事件类**（模板即时输出）：省易主、首都变迁、我方宣战/被宣战、同盟破裂、跨里程碑（省份数/人口/收入阈值）。
2. **决策类**（LLM 一句话）：回合决策执行结果回顾（如「进攻英格兰，占领 3 省，但国库告急」）。
3. **局势类**（LLM 短评，可选间隔回合）：地缘格局描述。
4. **里程碑类**（图表数据点）：排名上升/穿越纪元、人口层级突破。

旁白输出链路（双通道）：
- **通道 1 游戏内弹窗**：`narrator/narration_bridge`——向游戏进程投递文本。实现：游戏 jar 内注入 `NarrationBridge` 监听环形缓冲/本地文件，注入后每帧检查并 `CFG.toast.setInView(msg, COLOR)`。**注入方式**：附加类到游戏 jar 并重打包 AoC2.exe 尾段（或 `java -cp`+agent 实验；文档给出两种方案的验证步骤）。所有改动仅作用于用户本机单机副本。
- **通道 2 历史时间轴**：旁白+回合数据 → `narration_log.jsonl` → `narrator/timeline.py` 生成单文件 HTML（时间轴卡片：回合号、日期、旁白、关键数据、国名变色示意图），可嵌入直播/视频后期。

### 3.5 视频剪辑素材管线（video/）
- 每回合：地图窗口截图（`recorder/screenshots.py`，Windows `PrintWindow` API，已验证）；
- 产出包：`{session_dir}/turns/turn_{n}.png` + `turns.jsonl`（回合数据全量）+ `narration.jsonl` + `timeline.html`；
- `ffmpeg_timelapse.py`：把 `turns/*.png` 以回合日期为时间轴合成流畅变焦影片（`zoompan` 预设），叠加旁白轨道（`narration.jsonl` → burn-in 字幕可用 ASS 模板）——M4 里程碑。

## 4. 数据模型（recorder 的落盘 schema）

**`turn_{n}.json`（单回合全量）**
```json
{
  "turn": 17, "save_period": 3, "map": "Asia", "date": "1456",
  "player": {"civ_id": 206, "civ_tag": "eng", ...},
  "stats": {"provinces": [...], "population": [...], ...},   // 全文明快照
  "events": [{"type": "province_lost", "province_id": 3031, "to_civ": 235, "occupied": false}],
  "decision": [{"action": "declare_war", "target": "fra", "params": {...}, "reason": "..."}],
  "narration": {"toast": "...", "timeline": {"text": "...", "level": "major"}}
}
```

**`turns.jsonl`**：每行一个浓缩 `{turn, date, stats_of_interest, events, decision_ids, narration}`，用于剪辑打点与数据可视化。

## 5. 里程碑

| 阶段 | 内容 | 验收 |
|---|---|---|
| M0 | 仓库骨架 + `game_bridge` 打包（SaveDump 入库、`build.bat`、Python 包装） | 任意存档 `_S/_C_n` → 标准 JSON |
| M1 | `watchdog` + `turn_logger` + `screenshots`：全程录制器 | Agent 未介入也能录制人类一局 |
| M2 | `executor` + UI 配置 + `agent` 决策循环（DeepSeek） | 无人值守跑通 5+ 回合 |
| M3 | 叙事引擎 + 双通道（toast bridge + timeline.html） | 旁观 3 回合体验 & 历史时间轴生成 |
| M4 | 视频合成（ffmpeg 预设 + 字幕烧录） | 输出 1 分钟可剪辑成片素材 |
| M5 | Ollama 适配 / 校准工具 / README 英文版 / 发布 | 任意 LLM 可用，文档齐全 |

## 6. 技术选型

- Python 3.11（本机已备）；依赖 `watchdog`（fs 变化）、`Pillow`、`requests`/`httpx`（LLM）、`pyyaml`；屏幕截图可用内置 API 或 `mss`；输入用 `win32api`（pywin32）或纯 `user32` ctypes —— 选 **ctypes 零依赖**（已验证 mouse_event 链路）。
- Java：`SaveDump.java` 单文件，`javac --release 8` 编译，运行于游戏自带 JRE（classpath 含 `aoc2.jar`）。
- 游戏注入桥：Java8 字节码，类名 `age.of.civilizations2.jakowski.lukasz.NarrationBridge`（新增类，不改原逻辑）。

## 7. 合规与风险

- 本项目为**单机游戏自动化/数据研究工具**：只读解析存档、模拟本机输入、向本机游戏窗口投递提示；不含任何加密绕过/反编译分发/外挂对战功能。
- README 明确：仅适用于用户自有游戏副本与研究目的；不对游戏文件做修改时也可运行（旁白 toast 通道为可选增强）。
- 仓库不含任何凭据：`config.yaml.template` 占位符；推送前执行 `git log -p` 审查。

## 8. 待用户确认的决策点

1. 仓库名 `aoc2-ai-player` 是否 OK；README 语言（中文先行，英文后续 M5）。
2. 首版动作子集（M2）聚焦「宣战/和谈/征兵/投资/军队移动/结束回合」是否满意（大而全界面导航放 M5）。
3. 旁白默认模式：`hybrid`（事件走模板、决策/局势走 LLM）——成本与效果平衡。
4. 回合节拍：引导把自动存档设为 1（每回合落盘）；若用户不想动设置，录制器自动适配任意间隔（回合级数据仍完整，仅事件粒度受限）。
