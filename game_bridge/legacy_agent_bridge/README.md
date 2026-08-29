# Legacy AgentBridge（已归档，只读）

ASM javaagent 版引擎桥（FR-001 决议后退役）。本目录为**只读归档副本**，仅作：
- 迁移对拍参考（`/state` 字段集、动作实现、newGame 幂等守卫）
- 历史记录（v40 真机验证链路）

**当前启动流程已不再引用 -javaagent**（T011 classpath 模式）；`game_bridge/agent_bridge/` 原目录
保留原始构建（亦不再参与启动）。再次启用 = 旧 `start_game.bat` 的 `-javaagent` 路径（保留于
`start_game.bat` 的 `LEGACY_AGENT=1` 分支）。

内容：`agent-bridge.jar` / `build.bat` / `src/`（AgentBridge.java + Launcher.java，ASM 8.x shade）。
