# Phase 1 Data Model: AoC2 AI Player（机制层实体/状态机，深读增强版）

> 依据 research.md 深读结论；机制事实锚点见 `docs/mechanics.md`。

## 1. BridgeState（单一事实源，扩展自 FR-003）

| 字段组 | 字段 | 来源（已验证） |
|---|---|---|
| 回合 | `turn` `date` `turn_state` `in_game` | 现有桥 + `TurnStates` 枚举 |
| 资源存量 | `money` `move_points` `tech_points` **`diplomacy_points`** | `Civ.getDiplomacyPoints()` |
| 资源收入/回合 | **`income`**（`gold_in/gold_out` ← `getIncome/getExpenses/getBalance`；`diplo_delta` ← `getUpdateCivsDiplomacyPoints`；`move_set` ← set 公式复算） | 桥每回合聚合一次 |
| 国家 | `provinces` `units` `capital` `stability` `happiness` `rev_risk` `skills` | 现有 |
| 外交 | `treaties` `wars` `front_lines` `neighbors`（完整画像）+ `truce`（`getCivTruce`） | 现有 + 深读补 |
| **机制** | **`assimilates`**（province/turns_left/派系占比）· **`low_stability_list`** · **`war_score_res`**（双方 `getWarScore`）· `game_end`（`gameEnded`/eVICTORY） | `lAssimilates`/`lProvincesWithLowStability`/`War_GameData` |

对 Agent 最小可用投影 = {ledger, wars(truce), assimilates, low_stability, neighbors_简评, 胜负信号}。

## 2. ResourceLedger（FR-017①）

每回合行 `{turn, gold, move_pts, diplo_pts, tech_pts, income_gold, income_move, income_diplo}`；
ACTION_SPEC 成本标签 `query | gold | move | diplo | multi`（SC-010）。

## 3. MechanicsCatalog（L2 实例化；详见 docs/mechanics.md）

```yaml
mechanics:
  - id: internal_stability_gate      # 【安内门】先内政后战争（引擎 AI :255-261）
    verified: [source]
    trigger: low_stability_list 或 低幸福省数 > 0 → 推迟宣战，转同化/节日
    phases: [stable, assimilate_priority, defer_war]
  - id: war_cycle                    # 宣战→备战(3-6回合)→战役→和谈
    trigger: 预算>敌×0.695 且关系≤max(-50,-50/侵略) 且 无truce+接壤
    phases: [declare_gate, prepare_for_war(集结+征兵), campaign(前线评分/单省≥10), stale(39/49/299), peace_treaty(AI_UseVictoryPoints)]
  - id: assimilation_window          # 核心用户打法（已源码验证）
    trigger: 邻国 lAssimilates 非空 且 wars 中 → 突袭窗口
    phases: [evaluate(算其 cost/外交点/人口抽血), assemble, declare, assault_sequence]
    exit: Message_AssimilationEnd | 对方稳定恢复
  - id: diplo_economy                # 外交点节流 ≤170 顶（85+85×tech/4）
    phases: [refill_formula(基准/科技/排名/仇恨), cost_table, reserve]
  - id: invest_cycle                 # 4回合兑付、每省1单、move≥12/8
  - id: stability_revolt             # 稳定<0.62 风险升 & >0.16 起义（核心省除外）
  - id: tech_science                 # 8类技能点（效果表见 mechanics.md）
  - id: colonization_landgrab        # dipe14/move/gold；科技<0.8 惩罚；92 殖民红利
  - id: win_conditions               # VicotryManager 三选一 + gameEnded 轮询
```

- 每条带 `verified: [source|smoke]`，prompt 只引用 verified 条目（SC-009/宪法 VII）。
- `agent/mechanics/catalog.py` 校验：prompt tactic 引用必须命中目录。

## 4. Plan & Tactic

`Plan: {brief, turns[10]{offset, actions, note, tactic_ref}, base_provinces, start_turn, mechanic_phase}`
Tactic = 机制目录条目实例化（含窗口期参数、预算上限）。

## 5. AgentLoop 状态机

```
IDLE ──(panel start & in_game)──> ASSESS
ASSESS(/state+ledger+neighbors+机制谓词: 安内门/win/e/war_window)
  ├── 内政优先: stable_gate → 同化/节日/投资（引擎 AI 同款先手）
  └── war_window: analyze → prepare(预备期) → campaign
TACTIC_SELECT → SEQUENCE_EXPAND(每回合动作序列+资源预算行) → EXECUTE(/action, 回执OK)
→ RECORD(JSONL 附 mechanic_phase+tactic_ref) → END_TURN
事件重估(领土损失/战争开始或结束/assimilation_end/用户战略变化) → re-plan
LLM 连续失败(重试1次) → SKIP_TURN(确定性动作+推进+FAIL标记)   [任务E默认]
用户暂停 → WAIT
胜利/失败信号(gameEnded) → STOP+记录终局
```

## 6. SessionRecord（turns.jsonl 行）

`{turn, date, ledger, state_snapshot, neighbors, decisions[{action, tactic_ref}], results, plan_brief, mechanic_phase, war_score, events[war/peace/assim_end], tokens, tokens_cum, balance}`

## 7. DashboardState

每回合事件流（决策/回执/战争开始/和谈/同化结束/胜负）+ 资源台账（≤2s 轮询）；
指挥控件：strategy_text / gear(1-6) / paused（持久化 aoc2_strategy.txt + 暂停文件，机制同旧热键）。

## 8. 范式切换实体（2026-08-29 clarify——愿景 + 逐回合自主决策）

| 实体 | 字段 | 说明 |
|---|---|---|
| VisionPlan | brief(≤120字 / 10回合方向) / base_turn / generated_turn / trigger | FR-008 修订：仅文字愿景，无回合动作；重生成触发=领土损失/战略sig/决策类消息/10回合到期 |
| TurnDecision | turn / source(llm\|suggestion) / actions[] / reserve_after / cadence | 每回合自主决策（每 2 回合常规；事件触发立即；战争期每回合 FR-009） |
| ReservePolicy | gold_floor = max(0, 3×per_turn_net_income) / military_line = 1.2×提示/1.5×强制 | FR-017⑤ 动态储备；SC-011 判定 |
| DecisionContext | 白名单精简（FR-018）：ledger / 资源速查摘要 / 胜利进展压缩行 / 危险信号 / 前线评分 / 战术建议 / 常驻关系与历史追加行 | ≤6000 token；禁止叙事性铺陈 |

决策状态机：`INPUT_ORDERS → cadence_check(state_diff) → [决策|复用上次] → execute → reserve_guard(击穿→修复优先) → endTurn`；
`cadence=2 回合（常规）∪ 关键事件（wars 转变/领土损失/决策消息/战略变化/愿景到期）`。
