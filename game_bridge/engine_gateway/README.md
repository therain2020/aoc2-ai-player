# EngineGateway（源码级桥）

游戏引擎 API 直调层（2026-08-29 全量切换决议）：以新增桥接类形式随游戏 classpath 加载，
替代旧 ASM javaagent（归档至 `game_bridge/legacy_agent_bridge/`，仅留作对拍参考）。

## 运行时元数据（bootstrap 已验证）

| 项 | 值 |
|---|---|
| 游戏根 | `%USERPROFILE%\Downloads\Age of History II（含汉化）\Age of History II` |
| 游戏可执行 | `AoC2.exe`（即改名 jar，17.9MB） |
| 内嵌 JRE | 游戏根 `jre\bin\javaw.exe`（目标字节码 = Java 8） |
| 编译 JDK | 本机 JDK 21（`javac --release 8`；已用 T001 验证可产 gateway.jar） |
| 反编译源 | `%USERPROFILE%\Downloads\_aoc2_analysis\decompiled\`（CFR-0.152 同目录） |
| 游戏 jar 副本 | `%USERPROFILE%\Downloads\_aoc2_analysis\aoc2.jar`（= `.bridge/aoc2.jar` 同一份） |
| 桥端口 | 127.0.0.1:7187（`EngineGateway.DEFAULT_PORT`；`agent/bridge_client.py` 已对齐 T014） |
| 注入方式 | **T011 定稿（编码）**：主 = 引导型 javaagent（`GatewayPremain`，无 ASM/无 transformer/无权改动）；备 = `ENGINE_GATEWAY_CP=1` classpath（无自动启动，仅调试）；`LEGACY_AGENT=1` = 旧 ASM 桥（暂停使用）。实测定稿 = T015 |

## 构建

```bat
game_bridge\engine_gateway\build.bat     :: 依赖 repo\.bridge\aoc2.jar → 产出 gateway.jar
```

## 边界（FR-002）

- 仅新增桥接类（包 `agentbridge.gateway`）；禁止改动引擎核心类（CivData/GameData 等）逻辑
- 不暴露数值直改 API（setMoney/setResources/setTurn 等）
- 路由规划：`/state`（T007）`/action`（T008）`/plan` `/hud` `/command`（见 specs/001-aoc2-ai-player/contracts/engine-api.md）

状态: 骨架（T001-T006 完成；T007+ 实现中）
