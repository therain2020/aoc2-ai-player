# 已知缺陷/风险对账表（2026-08-29 重构期，T051 重写）

> 状态：fixed-pending-verify = 代码完成未真机验证（待 T015 冒烟一并复验）；
> closed = 代码+检查均闭环；open = 尚未处理。

## 对账表

| # | 缺陷/风险 | 状态 | 关联 |
|---|---|---|---|
| 1 | 战争分支「和谈」契约悬空（prompt 引导但无动作 → ActionError） | ✅ closed（T009：`PeaceTreaty_Data`+`AI_UseVictoryPoints`+`sendPeaceTreaty`；动作白名单 + prompt 恢复） | FR-014 |
| 2 | `bridge_client` 无 `new_game()`/`/plan` 裸 `_get` | ✅ closed（T014 端口统一 7187；`new_game()/push_plan()` 在桥） | FR-015 |
| 3 | AgentBridge `newGame` 需发两次才切视图 | 🟡 fixed-pending-verify（幂等守卫：视图已入 START/GAME 返回 already-in-game；待 T015 复验） | FR-015 |
| 4 | `peace_treaty` 引擎命令（无战争→no war；交战→对方 AI 处理） | 🟡 fixed-pending-verify（编译通过；非交战返回 FAIL(no war) 已单测；真机待 T015） | FR-014 |
| 5 | LLMProvider 基类缺 `last_usage/total/fetch_balance/track_balance` 类型声明（Pyright 报错） | ✅ closed（base.py 已声明） | 技术债 |
| 6 | `BridgeClient.hud()` 缺 line4/line5 参数（Java 侧已支持 5 行） | ✅ closed（client 已补齐） | FR-005 |
| 7 | 控制台中文乱码（GBK 显示层；文件内 UTF-8 正常） | ⚠️ open-known（`PYTHONIOENCODING=utf-8` 或 `python -X utf8`；panel/脚本已设置；属显示层低危） | 低危 |
| 8 | `_S` 100 回合滑动窗口：回合锚定依靠 `_T`（绝对 TURN_ID），禁止回退到 `_S` 行数判定 | ⚠️ 纪律项（勿回退） | M1 红牌 |
| 9 | 投资 retry 仅一次（窗口冲突重试）；FAIL 则整体动作标记失败并 re-plan | ⚠️ 行为说明（非 bug） | 冷却规则 |
| 10 | war 分支使用当回合 `/state` 快照（可能为回合初），主循环 3s 轮询 | ⚠️ 可接受（战争决策以引擎回执为准） | FR-009 |
| 11 | 视图保护 hook 恢复列表仅 5 个核心视图（其余 25+ `visible_*` 未逐个验证 getter） | ⚠️ 待评估（新桥为源码级、仅新增类；信息弹窗无需保护） | FR-007 |
| 12 | `hud_overlay.py`（tkinter 悬浮窗方案）已废弃 | ✅ 归档（不建议回退；HUD 注入走 new gateway） | 历史 |
| 13 | T033 `/state` 资源面（diplomacy_points/income/assimilates/低稳/truce/war_score/game_end）字段以引擎实读为准 | 🟡 fixed-pending-verify（源码级实现完成；真机 T015 读数锚定 research.md 未决 1） | FR-003 |
| 14 | T034 L1 外交全集（16 动作）点耗=菜单标记，`getCostOfCurrentDiplomaticActions` 为准 | 🟡 fixed-pending-verify（doc 标注；真机校准） | FR-014 |
| 15 | T035 assimilate/festival/colonize 前置校验（外点≥6/行动点≥8/diplo14+行动力+科技惩罚） | 🟡 fixed-pending-verify（引擎侧 FAIL 回执即防线；冒烟复核） | US4 |
| 16 | dashboard 旧端口 9110 已迁 → 7187 | ✅ closed（T023 重写时统一；dashboard-api.md 定稿 8080/7187） | T014 |
| 17 | LLM 连续失败无兜底（任务 E 语义） | ✅ closed（T043：重试 1 次 → SKIP_TURN + FAIL 记录 → 3 连败写暂停文件+告警） | US6 |
| 18 | panel 防重只查 pid 文件（残留进程漏杀） | ✅ closed（T044：pid 文件 + 命令行双匹配杀尽；网关 javaagent 进程一并管） | US6 |
| 19 | 主菜单预览/终局视图防错动作 | ✅ closed（T045：in_game=false 且 turn≤1 双判；game_end 信号；过渡视图清单快等） | US6 |
| 20 | 计划输出无机制引导（prompt 硬编码战术） | ✅ closed（T027/T028：catalog 9 机制 + mechanic_guidance 入 prompt，tactic_ref 校验） | FR-017③ |
| 21 | `docs/actions.md` 与 ACTION_SPEC 不一致（旧 11 动作口径） | ✅ closed（T047：30 动作全表 + COST_TAGS 五分类表；T038 四元自检 OK） | FR-016 |
| 22 | prompt 可能引用未验证机制 | ✅ closed（T049 guard：`invalid_refs_in` 断言 0；`test_mechanics_catalog`） | SC-009 |

## 待真机（T015 冒烟 / T032 / T042 / T046 / T052 验收项，需用户在场）

- 桥全链路真机冒烟（SC-006）：起游戏（boot-agent 模式）→ 面板 Start → ≥5 回合无 ClassNotFound/崩溃 → report.md
- US1 30 回合无人值守（turns.jsonl 完整 + dashboard 决策流可见）
- US2 dashboard 指挥：设战略③ → 下回合 HUD/上下文生效；暂停/恢复；重启 HUD 恢复
- US3 批量计划节奏：≥8 回合零调用；开战每回合恰 1 次 WAR 调用；周期消息不触发 re-plan
- US4 上下文完整：turns.jsonl 含 diplo_pts/assimilates/income；ACTION_SPEC 覆盖率 0 CRITICAL
- US5 timeline.html 含全部回合；dashboard ≤2s 刷新断言
- US6 杀尽/等待/暂停 + 3 连败告警人工复核
- M4 视频合成（ffmpeg 素材出片）— 里程碑尚未开发

## 观察基线（v40 桥，已验证）

- HUD 5 行布局：绿色输入行(仅输入时)/金色战略/白色余额Token/灰色战报×2，起始 y=62，行距 +25%。
- 自动推进：NextPlayerTurn clickEnd()、TURN_ACTIONS/LOAD_* 500ms 节流 clickEndTurn()、
  START 视图等 `Turn_CivsInRange.DONE_CIVS` 完成自动 `Menu_StartTheGame.done()`。
- 周期消息白名单：Message_TechPoints/Message_Uncivilized/Message_InvestDone/
  Message_Relations_Increase(_Ended)/Message_ProvincesNotSupplied。
