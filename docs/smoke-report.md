# 真机冒烟报告（T015 / SC-006，2026-08-29）

> 结论：**PASS**——桥→状态→决策→执行→endTurn→推进 全链路真机闭环，5+ 回合无崩溃。
> 环境：gateway.jar（15:12 重打包，含双逗号修复）；Agent 3 个独立后台实例（具名 run-1527/1530）；
> 对局：Asia / 文明 133，由 turn 13 推进至 turn 24。

## 验收记录

| 回合 | 视图 | 决策 | 执行 | endTurn | 异常 |
|---|---|---|---|---|---|
| 13 | INPUT_ORDERS | PLAN（10 回合批量计划，含国力对比 brief） | recruit_army 200 OK | ✓ | — |
| 17 | INPUT_ORDERS | plan[1]（收益+征兵） | 1/2 OK（invest FAIL=引擎拒绝负金库；recruit OK） | ✓ | — |
| 18/20/22/23 | INPUT_ORDERS | plan 续（投资/征兵） | 1/2 OK ×4 | ✓ | — |
| 24 | INPUT_ORDERS | plan 续 | （记录在案） | ✓ | 本轮后主动停止 Agent（冒烟收尾） |

- 消息路由：`AUTO MSG [Message_Relations_Insult] -> context only` ×2（零 LLM 消耗），Periodic/TechPoints 类不触发重规划 ✓
- 会话记录：`sessions/20260829-153048-agent-run-1530/turns.jsonl`——7 行（1 plan + 6 回合）；
  字段完整：decision/results/ledger（含 income gold=-3、diplo=8）/mechanic_phase=peace_economy/tactic_ref/tokens/tokens_cum ✓
- LLM 调用纪律：仅 1 次 PLAN/批次；无假失败重规划（修复前曾因回执判定 bug 每回合白烧 1 次）

## 本冒烟修复/确认的问题

1. **[closed] /state 双逗号**：truce 尾逗号 + contract extras 前导逗号 → JSON 非法 → 面板/主循环全崩。
2. **[closed] game_end 字段真值陷阱**：`"game_end":{"ended":false}` 是 dict——`if st.get("game_end"):` 恒真 →
   主循环每轮 sleep(10) 死等。改为 dict/bool 双形态判定。
3. **[closed] 回执判定**：新桥回执 JSON 形态 `{"result":"OK",...}`，`str().startswith("OK")` 恒假 →
   动作全被判失败 → 每回合额外重规划。统一 `result_ok()`（兼容 JSON/pipe/dict）。
4. **[closed] 面板 3 项**：Stop agent 不再杀游戏（游戏单独菜单 5）；Status 实时扫描 agent 进程 +
   最新回合摘要 + 暂停/战略文件；启动加 `-u` 保证日志即时落盘。
5. **[observed] 引擎行为正确性**：金库 -90 时 invest/investDev 被引擎拒绝（前置金>0）——非桥 bug；
   Agent 侧应避免负金库下重复投资（见下）。

## 遗留观察项（非阻塞）

- **重复无效 invest**：负金库回合 LLM 仍每回合建议 invest（1/2 重复失败）——建议 Agent 侧预算护栏：
  金<500（或 income.gold<0）时 prompt 追加"禁止金币类动作"。
- **回合跳号**：18→20（19/21 无回合行）——引擎/多步推进所致，agent 侧无崩溃；待观察与 autosave_in
  相关的回合级联判定。
- **桥 FAIL 无原因**：FAIL 回执 detail 为空（排查不便）——建议 Java 侧 fail 带 reason 字段（下次重打包时带上）。
- 金库 -90 的对局已"伤"（前几次试运行时用未修复判定打磨了操作）——后续观察建议新开/载入干净存档。

## 遗留验收（其余 SC 段）

按 quickstart.md：US1 30 回合 / US2 dashboard 指挥 / US3 批量计划节奏 / US4 上下文完整 /
US5 timeline+dashboard / US6 三防线人工复核 —— 冒烟已覆盖每类核心链路，全量打卡待用户安排。
