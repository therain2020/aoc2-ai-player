"""战场图生成器 — 省份关系可视化（前线带 + 各边兵力标注）。

Reads live /state (after army getter fix: getArmyCivID) and renders a single-file
HTML battle map: 我方省(绿)/敌省(红) 节点圆，蓝边=战线（我N兵 vs 敌M兵），
节点大小=驻军。局部力导向布局（确定性 seed）。

Usage: python scripts/battle_map.py [--out sessions/battle_map.html]
"""
import argparse
import json
import math
import random
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BRIDGE = "http://127.0.0.1:7187"


def fetch_state() -> dict:
    with urllib.request.urlopen(BRIDGE + "/state", timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def build_nodes(st: dict):
    """Nodes: my garrison provinces (armies_overview) + front ends; color by owner."""
    nodes: dict[int, dict] = {}
    for a in st.get("armies_overview") or []:
        pid = int(a.get("prov"))
        nodes[pid] = {"id": pid, "mine": True, "counts": [int(a.get("army") or 0)]}
    for f in st.get("front_lines") or []:
        frm, to = int(f.get("from")), int(f.get("to"))
        for pid, is_mine in ((frm, True), (to, False)):
            n = nodes.setdefault(pid, {"id": pid, "mine": is_mine, "counts": []})
            n["mine"] = n["mine"] and is_mine
        nodes[to]["enemy_civ"] = f.get("civ")
        nodes[frm]["counts"].append(int(f.get("my_units") or 0))
        nodes[to]["counts"].append(int(f.get("enemy_units") or 0))
    return nodes


def html_map(st: dict) -> str:
    nodes = build_nodes(st)
    edges = [{"from": int(f["from"]), "to": int(f["to"]),
              "my": int(f.get("my_units") or 0), "en": int(f.get("enemy_units") or 0)}
             for f in st.get("front_lines") or []]
    ids = sorted(nodes)
    seed = 42
    pos = {}
    for i, pid in enumerate(ids):
        rnd = random.Random(seed + i * 17)
        ang = 2 * math.pi * i / max(len(ids), 1)
        pos[pid] = (400 + 300 * math.cos(ang) + rnd.randint(-120, 120),
                    270 + 200 * math.sin(ang) + rnd.randint(-90, 90))
    svg_parts = [
        '<svg width="800" height="560" xmlns="http://www.w3.org/2000/svg">',
        '<rect width="800" height="560" fill="#0f1218"/>',
        '<text x="16" y="28" fill="#f2c14e" font-size="18">战场图 · 前线带（T%(turn)s · 我%(me)s 兵 · g%(g)s）</text>'
        % {"turn": st.get("turn"), "me": st.get("units"), "g": st.get("money")},
    ]
    for e in edges:
        a, b = pos[e["from"]], pos[e["to"]]
        color = "#4fc3f7" if e["my"] >= 10 else "#f0a1a1"
        svg_parts.append(
            f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" stroke="{color}" '
            f'stroke-width="{max(1, math.log10(max(e["my"], 10)))}" opacity="0.75"/>')
        svg_parts.append(
            f'<text x="{(a[0]+b[0])//2}" y="{(a[1]+b[1])//2}" fill="#ffd54f" font-size="11">'
            f'我{e["my"]}v敌{e["en"]}</text>')
    for pid, n in nodes.items():
        x, y = pos[pid]
        r = 12 + math.log10(max(max(n["counts"], default=1), 1)) * 5
        fill = "#2e6e4e" if n["mine"] else "#8e3a3a"
        svg_parts.append(
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="#fff" stroke-width="1"/>')
        svg_parts.append(
            f'<text x="{x}" y="{y + 4}" fill="#fff" font-size="12" text-anchor="middle">{pid}</text>')
    svg_parts.append("</svg>")
    instructions = (
        "<p>图例：绿=我方省 红=敌省 圆大小=前线驻军 蓝边=我方≥10兵可攻 红边=我方<10兵（不可攻）</p>"
        "<p>注：本图数据来自桥 /state；若兵力全 0 表示桥端 army 读取器尚未重打包（见 45729d1 修复）。</p>")
    return ("<!DOCTYPE html><html lang='zh'><head><meta charset='utf-8'>"
            "<title>AoC2 战场图</title></head><body style='background:#101418;color:#dde2ea'>"
            + "\n".join(svg_parts) + instructions + "</body></html>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "sessions" / "battle_map.html"))
    args = ap.parse_args()
    st = fetch_state()
    html = html_map(st)
    Path(args.out).write_text(html, encoding="utf-8")
    print(f"written: {args.out}")
    print("front pairs:", len(st.get("front_lines") or []),
          "| my_units 总和:", sum(int(f.get("my_units") or 0) for f in (st.get("front_lines") or [])))
    print("我方有兵省:", len(st.get("armies_overview") or []))


if __name__ == "__main__":
    main()
