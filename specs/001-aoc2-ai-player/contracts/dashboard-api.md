# Contract: Dashboard Command & Monitor API（Python，127.0.0.1:8080）

> dashboard = 新定位的主界面（宪法 IV.1 修订记录）：指挥 + 监控；游戏内 HUD 只读（带过）。
> 视图数据 ≤2s 轮询；文件通道保持与旧机制一致（aoc2_strategy.txt / aoc2_plan.txt / aoc2_hud.txt）。

## GET / 与静态面
- 面板布局：资源台账（存量+收入）、国家状态（国土/军力/稳定度/科技）、决策流（每回合 决策→回执→战报）、计划面板（10 回合 + tactic_ref）、Token/余额图、暂停开关、六档战略、文本战略输入框。

## GET /api/state
→ bridge /state + 本地缓存（TTL 2s）。统一返回 `{turn, date, ledger, state, mechanic_phase, last_tokens, balance}`。

## POST /api/command
```json
{"cmd": "strategy_text", "value": "优先吞并西南邻国"}   // 写 aoc2_strategy.txt
{"cmd": "gear", "value": 3}                            // 六档 → aoc2_strategy.txt（同文件段）
{"cmd": "pause", "value": true|false}                  // 切换暂停文件（END 语义）
```
响应 `{"ok": true}`；校验 value 合法（档位 1-6、文本非空）。

## GET /api/plan
→ 桥内存计划（POST /plan 的数据 + base_provinces/start_turn），面板呈现。

## POST /api/assess  （未来项，导演模式预留）
→ 手动触发一次机制评估（默认不暴露，防预算滥用）。

## 与桥关系
dashboard 不直接触碰引擎——只读桥 GET /state、GET /hud；写文件通道；/action 由 Agent 主循环执行（单实例裁决，宪法 V）。
