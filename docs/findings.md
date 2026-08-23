# 技术发现档案（来自源码研究与实测）

## UI 缩放机制

- 入口：`config.ini` 的 `UISCALE`（`-1` 自动 / 1..5 档）
- 档位 → BUTTON_WIDTH：90 / 120 / 160 / 180 / 212 px（AoCGame.java:250-251）
- `BUTTON_HEIGHT` = `btn_menu.png` 资源高度；`GUI_SCALE = BUTTON_HEIGHT/68`（AoCGame.java:252）
- `PADDING = 5*GUI_SCALE`，`FONT_MAIN_SIZE = 18*GUI_SCALE`（字体同步缩放）
- 实测：UISCALE=3（160px 按钮）适合 1080p 截图识别与坐标点击

## 关键快捷键（源码 hover 提示确认）

- `SPACE` = 结束回合（Button_Game_NextTurn hover: "Shortcut: SPACE"）

## 游戏主界面（Menu_InGame_ProvinceInfo）

- 结束回合按钮：`x = GAME_WIDTH - tempWidth - PADDING - minimapWidth, y = PADDING`（顶部右区）
- 选中省份 → 底部省名条（Text）；省名条上方 hover 面板显示省份详情

## 存档/回放数据（已实测）

- 见 plans/2026-08-23-aoc2-ai-player.md §2.2；`SaveDump` 直接反序列化输出 JSON
