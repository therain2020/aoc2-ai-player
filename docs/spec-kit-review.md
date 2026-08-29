# spec-kit 审视报告（归档 + 修复进展）

> 2026-08-29 | spec-kit v1.0.1（仓库同步 upstream main 51e52be6）
> 审视数据源：会话 b8bbafe2（用户全部拍板）+ 代码现状（v40）+ 文档三方对照。
> 本文件为审视结论的持久化记录；修复进展已同步到 `specs/001-aoc2-ai-player/tasks.md`。

## SDD 基础设施（初审：严重不达标 → 已修复）

| spec-kit 必备件 | 初审 | 现状（2026-08-29） |
|---|---|---|
| `.specify/memory/constitution.md` | ❌ 不存在 | ✅ 宪法 v1.0（8 条原则，源：会话用户拍板） |
| `specs/*/spec.md` | ❌ 不存在 | ✅ `specs/001-aoc2-ai-player/spec.md`（6 故事 + FR-001~016 + SC-001~008） |
| `plan.md`（spec-kit 格式） | ⚠️ 自定格式草案、过时 | ✅ 同目录 plan.md（4 Phase） |
| `tasks.md` | ❌ 不存在 | ✅ 同目录 tasks.md（T001-T106，Phase 0/2/3 已勾选） |

## 检测发现与修复状态（analyze 范式）

| ID | 级别 | 发现 | 状态 |
|---|---|---|---|
| D1 | 🔴 CRITICAL | 战争和谈契约悬空（prompt 引导 → 无动作 → ActionError 崩溃） | ✅ 修复：`peace_treaty` 引擎命令（`PeaceTreaty_Data` + `AI_UseVictoryPoints` + `sendPeaceTreaty`，AI 同款三步）+ 动作白名单 + 客户端封装；待真机联测 |
| D2 | 🟠 HIGH | 文档互斥（actions.md 二期表与实现矛盾、READMЕ 残留模拟点击） | ✅ 修复：actions.md 重写（11 动作权威表）；README 口径修正 |
| D3 | 🟠 HIGH | 未提交 22 项（AgentBridge +729 / Launcher +133 / agent/ 等） | ⏳ 待用户授权提交（T010-T014） |
| D4 | 🟠 HIGH | README 头部"模拟本机键鼠输入" | ✅ 已改（引擎 API 直调） |
| D5 | 🟡 MEDIUM | 接口面不同步（无 new_game/裸 _get） | ✅ `new_game()`/`push_plan()` + newGame 幂等守卫 |
| D6 | 🟡 MEDIUM | 零测试 | ✅ tests/ 17 passed（parse/state 全绿） |
| D7 | 🟡 MEDIUM | 诊断脚本入库 / pending_fixes 过时 | 🟡 已重写 pending_fixes；`scripts/_*.py` 清理归入 T013 |
| D8 | 🟡 MEDIUM | LLMProvider 类型声明缺失（Pyright） | ✅ base.py 补齐 last_usage/total/fetch_balance/track_balance |
| D9 | 🟡 MEDIUM | hud() 客户端缺 line4/5 | ✅ 已补齐（Java 侧 5 行已支持） |

## 遗留（需真机/用户在场）

- T103/T104：30 回合冒烟 + SC-001~005 打卡（需游戏窗口；turns.jsonl 证据采集）
- 审视方法学注释：`specify init --here --force --non-interactive --integration claude`
  初始化；工作流与 skills 见 `.specify/`、`.claude/skills/speckit-*/`。
