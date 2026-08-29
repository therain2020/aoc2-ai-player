"""Always-on-top HUD overlay (separate window, zero game-engine risk).

Usage: python -m narrator.hud_overlay [--session <dir>] [--x 40] [--y 40]
Shows: balance + tokens line, latest turn brief, previous turn brief.
Left-click-drag to move; right-click to close.
"""
import argparse
import json
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BRIDGE = "http://127.0.0.1:9110"


def fetch_json(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return {}


def get_session() -> str:
    base = Path(REPO / "sessions")
    dirs = [d for d in base.iterdir() if d.is_dir() and "agent" in d.name]
    return str(max(dirs, key=lambda d: d.stat().st_mtime)) if dirs else ""


def compute_hud():
    st = fetch_json(BRIDGE + "/state")
    last = {"prompt_tokens": 0, "completion_tokens": 0, "cache_hit_tokens": 0}
    balance = None
    briefs = []
    try:
        with open(Path(get_session()) / "turns.jsonl", encoding="utf-8") as f:
            for line in f:
                try:
                    t = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if t.get("tokens_cum"):
                    last = dict(t["tokens_cum"])
                if t.get("balance") is not None:
                    balance = t["balance"]
                if t.get("brief"):
                    briefs.append(f"T{t.get('turn')} {t['brief'][:26]}")
    except Exception:
        pass
    u = last
    line1 = (f"余额 ¥{balance:.2f}" if balance is not None else "余额 --") + \
            f" ｜ Token 入{u.get('prompt_tokens',0)/1e6:.3f}M 出{u.get('completion_tokens',0)/1e6:.3f}M"
    if u.get("cache_hit_tokens", 0) > 0:
        line1 += f"（缓存 {u['cache_hit_tokens']/1e6:.3f}M）"
    line2 = briefs[-1] if briefs else ""
    line3 = briefs[-2] if len(briefs) > 1 else ""
    return line1, line2, line3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--x", type=int, default=40)
    ap.add_argument("--y", type=int, default=300)
    args = ap.parse_args()

    import tkinter as tk

    root = tk.Tk()
    root.overrideredirect(True)          # frameless
    root.attributes("-topmost", True)
    try:
        root.attributes("-alpha", 0.92)
    except tk.TclError:
        pass
    root.configure(bg="#101520")
    root.geometry(f"520x84+{args.x}+{args.y}")

    lbl1 = tk.Label(root, text="...", fg="#f2c14e", bg="#101520",
                    font=("Microsoft YaHei", 11, "bold"), anchor="w", justify="left")
    lbl2 = tk.Label(root, text="", fg="#dbe4f2", bg="#101520",
                    font=("Microsoft YaHei", 10), anchor="w", justify="left")
    lbl3 = tk.Label(root, text="", fg="#9fb2cc", bg="#101520",
                    font=("Microsoft YaHei", 10), anchor="w", justify="left")
    for w in (lbl1, lbl2, lbl3):
        w.pack(fill="x", padx=10)

    def on_drag_start(e):
        root._dx, root._dy = e.x_root - root.winfo_x(), e.y_root - root.winfo_y()

    def on_drag(e):
        root.geometry(f"+{e.x_root - root._dx}+{e.y_root - root._dy}")

    root.bind("<Button-1>", on_drag_start)
    root.bind("<B1-Motion>", on_drag)
    root.bind("<Button-3>", lambda e: root.destroy())

    import ctypes

    user32 = ctypes.windll.user32

    def force_top():
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
        user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)  # TOPMOST|NOMOVE|NOSIZE

    def refresh():
        force_top()
        l1, l2, l3 = compute_hud()
        lbl1.config(text=l1)
        lbl2.config(text=l2)
        lbl3.config(text=l3)
        root.after(2000, refresh)

    refresh()
    root.mainloop()


if __name__ == "__main__":
    main()
