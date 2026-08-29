# Contract: EngineGateway REST（源码级桥，127.0.0.1）

> 与 L1/L2 配套：动作 = 玩家等价全集；响应回执以引擎返回为准（OK/FAIL，宪法 VII.3）。
> 所有引擎方法签名以反编译源码行号为准（research.md 决策 1 表）。

## 生命周期
- 桥随游戏启动（EngineGateway 编译进 classpath）；端口固定（同旧桥）；Agent 只在 `in_game=true` 且 `turn_state=INPUT_ORDERS` 时行动。

## GET /state
返回 BridgeState 全量（data-model §1）。新增字段（相对旧桥）：`diplomacy_points`、`income.*`、`assimilates`（同化列表：province_id/turns_left/population）。

## POST /action
```json
{"action": "<name>", "params": {}}
```
| 动作族 | 示例 | 消耗标签 |
|---|---|---|
| 军事 | declare_war / recruit_army / move_army / disband_army / prepare_for_war / call_to_arms | move/gold/multi |
| 战争收尾 | **peace_treaty**（照 AI 范式：PeaceTreaty_Data + AI_UseVictoryPoints 自动分账） | diplo |
| 内政 | move_capital / invest / invest_dev / invest_tech(8类) / construct(7类) / **assimilate**(province_id, num_of_turns) | gold/move/diplo |
| 外交 | offer_alliance / **send_gift / send_insult / trade_request / nonaggression_pact / offer_vasalization / military_access_give/ask / improve_relations / decrease_relations / support_rebels / ultimatum / civilize / form_civilization / proclaim_independence** | diplo/multi |
| 查询 | state / front_lines / neighbor(画像) / province_detail / assemble_assessment | query（零成本） |

响应：`{"result": "OK"|"FAIL", "log": "...", "detail": {引擎侧信息}}`——FAIL 时 Agent 可读回反馈。

## POST /plan（计划内存通道，dashboard 面板可查）
```json
{"brief": "...", "turns": [{"offset": 0, "actions": [{"action": "...", "params": {}}], "note": "...", "tactic_ref": "..."}], "base_provinces": [...], "start_turn": 1}
```
校验：动作必须 ∈ ACTION_SPEC；tactic_ref 必须 ∈ MechanicsCatalog[verified]（SC-009）。

## GET /hud
HUD 数据流（金额/Token/战报/战略档）→ 游戏内只读渲染 + aoc2_hud.txt 持久化（重启恢复）。

## POST /narration（toast 热提示，旧旁白链路）
```json
{"text": "..."}
```
响应 `{"ok": true}`；兼容查询形式 `GET /narration?text=...`（`agent/bridge_client.py` 现用）。
颜色/时长沿用现有 toast（CFG.toast.setInView 默认 2s）。

## 兼容面约定（T014）
- 桥端口固定 **7187**（`EngineGateway.DEFAULT_PORT`；旧桥 9110 不再使用）
- 旧桥为 `GET /action?cmd=<pipe>`（如 `declareWar|3|false`）；EngineGateway 同时提供
  **POST /action JSON**（本文件为准）与 **GET /action?cmd= 管道兼容路由**（桥端 shim），
  保证 `agent/main.py` 等旧调用零改动路径；`bridge_client.py` 逐步收敛到 POST。

## 边界（FR-002）
- 数值直改类（setMoney/setResources/setTurn/改地图/改文明数据）**不提供**——导演模式未来单独 allowlist。
- 空耗动作（零收益循环动作）由预算提示词治理，不须桥拦截。
