# aoc2-ai-player

让 LLM Agent 作为玩家玩《文明时代2》(Age of Civilizations II, 原版 Java 版)，
全程自动记录每回合数据（领土变动、各项统计、决策事件），支持实时旁观、
旁白解说（游戏内弹窗 + 历史时间轴）与视频剪辑素材导出。

> 本项目为单机游戏自动化/数据研究工具：只读解析本地存档、模拟本机键鼠输入、
> 向本机游戏窗口投递提示；不含任何对战外挂或远程服务。

## 工作原理

游戏内建「历史回放」数据（timelapse），每次存档落盘：

- `TS/<id>_S` —— 每回合全文明统计（省份/人口/排名/科技/收支）
- `TS/TURN/<id>_C_<n>` —— 每回合省份易主事件

`game_bridge/SaveDump`（Java，运行于游戏自带 JRE）把存档反序列化为 JSON，
供离线回放与数据归档；**Agent 的实时操作通过 AgentBridge（javaagent 注入）
直调游戏引擎 API**（宣战/征兵/移动/投资/结束回合），不占用键鼠——旁观者可自由
点击地图查看信息。

```
AgentBridge(引擎 API 直调) ← /state、/action ← LLM 决策循环
                                        ↓
       每回合 JSONL + 截图（后台抓帧）+ 旁白(toast 弹窗 + 时间轴)
```

## 快速开始

```bash
pip install -e .                       # Python 3.11
cp config.yaml.template config.yaml    # 填 game.root / llm 配置
python -m recorder.main                # 监控并录制已打开的游戏存档
```

## 目录结构

- `game_bridge/`   存档反序列化桥（SaveDump.java, build.bat, dump_save.py）
- `game_bridge/agent_bridge/`  AgentBridge 注入组件（javaagent：引擎 API + toast + 旁白）
- `recorder/`      回合录制（turn_logger, watcher, screenshots, session）
- `agent/`         LLM 决策循环（llm/ provider 抽象：OpenAI 兼容 / Ollama）
- `narrator/`      旁白引擎（事件模板 + LLM 短评 + toast 通道）
- `video/`         ffmpeg 素材合成

## 里程碑

M0 数据桥 → M1 录制器 → M2 Agent 循环 → M3 旁白双通道 → M4 视频合成 → M5 发布

## 致谢与参考

- 游戏：《Age of Civilizations II》 Łukasz Jakowski Games
- 数据格式来自对游戏自身存档/回放系统的只读研究
