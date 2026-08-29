# 已知缺陷清单（取代旧版"M2 验证轮探索清单"）

> 旧清单（v6 桥探索）全部条目已在 v8-v33 落地关闭，本文档重写为
> "当前已知缺陷对账表"，状态列 = open/fixed-pending-verify/closed。

## 对账表

| # | 缺陷/风险 | 状态 | 关联 |
|---|---|---|---|
| 1 | 战争分支"和谈"契约悬空（prompt 引导但无动作 → ActionError 崩溃） | ✅ closed（2026-08-29：实现 `peace_treaty` 引擎命令 + 动作白名单 + prompt 恢复引导） | FR-014 / T001-T003 |
| 2 | `bridge_client` 无 `new_game()` / `/plan` 裸 `_get` | ✅ closed（新增 `new_game()`/`push_plan()`） | FR-015 / T020 |
| 3 | AgentBridge `newGame` 需发两次才切视图 | 🟡 fixed-pending-verify（新增幂等守卫：视图已入 START/GAME 即返回 already-in-game；待真机复验） | FR-015 / T021 |
| 4 | `peace_treaty` 引擎命令（`PeaceTreaty_Data`+`AI_UseVictoryPoints`+`sendPeaceTreaty`） | 🟡 fixed-pending-verify（编译通过；待真机：非交战返回 no war、交战时 OK 且对方 AI 处理） | FR-014 |
| 5 | LLMProvider 基类缺 `last_usage/total/fetch_balance/track_balance` 类型声明（Pyright 报错） | ✅ closed（base.py 已声明） | 技术债 |
| 6 | `BridgeClient.hud()` 缺 line4/line5 参数（Java 侧已支持 5 行） | ✅ closed（client 已补齐；java 侧 hudLine4/5 已验证） | T020 |
| 7 | 控制台中文乱码（GBK 显示问题；文件内 UTF-8 正常） | ⚠️ open-known（显示层问题，需 `PYTHONIOENCODING=utf-8`；bridge 日志已改 UTF-8） | 低危 |
| 8 | `_S` 100 回合滑动窗口：回合锚定依靠 `_T`（绝对 TURN_ID），禁止回退到 `_S` 行数判定 | ⚠️ 纪律项（勿回退） | M1 红牌修复 |
| 9 | 投资 retry 仅一次（窗口冲突重试）；若仍 FAIL 则整体动作标记失败并 re-plan | ⚠️ 行为说明（非 bug） | 冷却规则 |
| 10 | war 分支使用当回合 `/state` 快照（数据可能为回合初），主循环 3s 轮询 | ⚠️ 可接受（战争决策以引擎回执为准） | FR-009 |
| 11 | 视图保护 hook 恢复列表仅 5 个核心视图（Rank/History/Wars/MilitaryAlliances/WarDetails） | ⚠️ 待评估（其余 25+ visible_* 未逐个验证 getter 存在；AI 回合点击省份的信息弹窗无保护需求） | FR-007 |
| 12 | `hud_overlay.py`（tkinter 悬浮窗方案）已废弃 | ✅ 归档（不建议回退；游戏独占全屏下原生 HUD 注入已在 AoCGame.render） | 历史 |

## 观察基线（v40 桥，已验证）

- HUD 5 行布局：绿色输入行(仅输入时)/金色战略/白色余额Token/灰色战报×2，起始 y=62，行距 +25%。
- 键位：Insert(战略输入)/PageUp(六档)/PageDown(计划)/END(暂停)。
- 自动推进：NextPlayerTurn clickEnd()、TURN_ACTIONS/LOAD_* 500ms 节流 clickEndTurn()、
  START 视图等 `Turn_CivsInRange.DONE_CIVS` 完成自动 `Menu_StartTheGame.done()`。
- 周期消息白名单：Message_TechPoints/Message_Uncivilized/Message_InvestDone/
  Message_Relations_Increase(_Ended)/Message_ProvincesNotSupplied。
