# Quickstart: AoC2 AI Player 真机验收指南（机制层闭环）

> 目标：从"桥冒烟"到"30 回合无人值守 + 机制场景过检 + 看板指挥生效"。
> 前置：游戏根 = `%USERPROFILE%\Downloads\Age of History II（含汉化）\Age of History II`；
> 反编译源 = `%USERPROFILE%\Downloads\_aoc2_analysis\decompiled\`；Python 3.11；DeepSeek config.yaml。

## 0. 构建（一次性）
```bat
game_bridge\engine_gateway\build.bat        :: --release 8 → gateway.jar
```
产出 `gateway.jar`（新增类，不改原游戏字节码）。

## 1. 桥冒烟（SC-006 基线：≥5 回合无崩溃）
```bat
panel Start → start_game.bat "<game root>" 以新 classpath 启动
curl 127.0.0.1:<port>/state
```
**验收**: /state 含 `diplomacy_points`、`income.*`、`assimilates`（新字段上报）；观察 5+ 回合无 ClassNotFound/崩溃。

## 2. L1 动作冒烟（SC-009/010）
真机内调：`declare_war` / `move_army` / `recruit_army` / `invest` / **`peace_treaty`** / **`assimilate`** / `send_gift` / `trade_request`。
**验收**: 每动作回执 `{"result":"OK"}`（FAIL 允许——引擎规则拒绝属正常，须有 log）;ACTION_SPEC 与 docs/actions.md 逐条一致（SC-007）。

## 3. 机制场景过检（L2，QC 主线）
- **同化窗口**: 人造对局（我方邻国战争结束进入同化）→ 该回合 `assimilates` 非空、我方评估输出"突袭窗口"判定 → 执行动作序列（turns.jsonl 的 `tactic_ref=assimilation` + 决策依据文本可 grep）。
- **渔翁得利端到端（可选强制）**: 挑动两强开战 → 胜者同化期突袭 → 回执与领土变化落盘。
**验收**: `docs/mechanics.md` 圈定的机制均带 `[source]` 或 `[smoke]` 标记；无标记实例不出现在 prompt。

## 4. 无人值守 30 回合（SC-001~006 打卡）
```bat
agent\panel.py Start
```
**验收**: SC-001（无突发 10 回合 ≤6 决策调用：每 2 回合常规+愿景 1 次）、SC-002（战争期每回合一战调用+move_army 邻接）、SC-004（无进程堆积）、SC-005（输出 ≤1500；决策上下文输入 ≤6000；前缀命中 ≥80%）、SC-006（无崩溃）。

## 4b. 范式切换过检（2026-08-29 clarify——SC-011 / FR-018）
1. **愿景式计划**: dashboard 计划面板仅显示文字愿景（≤120 字/10 回合）；无回合动作表。
2. **决策节拍**: 稳定期 turns.jsonl 决策行间隔 = 2 回合；关键事件（领土损失/战争转变/决策消息/战略变化/愿景到期）立即触发决策行。
3. **储备纪律**: 任意 10 回合窗口，金 <3×单回合净收入的回合数 ≤2（越线回合必须出现"修复收入/收缩开支"类决策）；1.5× 军力强制线触发回合必有重规划/应对记录。
4. **上下文精炼**: 抽样决策调用的输入 token ≤6000；上下文不含文档全文/重复段落（可 grep 审计——叙事性描述不落 DecisionContext 白名单外字段）。

## 5. 看板指挥 + HUD 只读（US1/US2）
浏览器开 8080 → 设战略③ → 下一回合 HUD 金色行更新 + LLM 上下文【战略指示】→ 暂停/恢复生效 → 重启游戏 HUD 恢复。
**验收**: ≤2s 刷新（US1-3）；计划面板展示 plan+tactic_ref（US2-4）。

## 6. 提交前
- `git log -p` 逐文件 6 类敏感信息审查；config.yaml 不入库。
- analyze 复审（spec/plan/tasks + research 附件一致性，无 CRITICAL/HIGH）——SC-008。
