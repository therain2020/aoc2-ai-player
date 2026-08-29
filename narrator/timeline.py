"""Generate a single-file HTML narration timeline from an agent session.

Usage:
    python -m narrator.timeline [--session <dir>] [--out timeline.html]
    (default: newest session under ./sessions; out ./timeline.html)
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def find_newest_session(base: Path) -> Path:
    dirs = [d for d in base.iterdir() if d.is_dir() and "agent" in d.name]
    if not dirs:
        raise SystemExit(f"no agent sessions under {base}")
    return max(dirs, key=lambda d: d.stat().st_mtime)


def load_turns(session_dir: Path) -> list:
    path = session_dir / "turns.jsonl"
    if not path.exists():
        return []
    turns = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                turns.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return turns


def render(turns: list, session_name: str) -> str:
    cards = []
    for t in turns:
        ts = datetime.fromtimestamp(t.get("ts", 0)).strftime("%H:%M:%S") if t.get("ts") else ""
        state = t.get("state", {})
        stats = "金币 {money} · 省份 {provinces} · 军队 {units}".format(
            money=state.get("money", "?"), provinces=state.get("provinces", "?"),
            units=state.get("units", "?"))
        actions = "".join(
            f'<span class="chip">{a.get("action")}: {json.dumps({k: v for k, v in a.items() if k != "action"}, ensure_ascii=False)}</span>'
            for a in t.get("decision", []))
        results = "".join(
            f'<span class="res {("ok" if r.get("result","").startswith("OK") else "fail")}">{r.get("result", "")}</span>'
            for r in t.get("results", []))
        cards.append(f"""
        <div class="card">
          <div class="head">
            <span class="turn">回合 {t.get('turn')}</span>
            <span class="ts">{ts}</span>
            <span class="stats">{stats}</span>
          </div>
          <div class="brief">{t.get('brief', '')}</div>
          <div class="actions">{actions}</div>
          <div class="results">{results}</div>
        </div>""")
    return """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>AI 游玩旁白时间轴</title>
<style>
 body{{font-family:"Microsoft YaHei",sans-serif;background:#14171d;color:#e6e8ea;margin:0;padding:24px;max-width:860px;margin:0 auto}}
 h1{{font-size:20px;color:#f2c14e;border-bottom:1px solid #2a2f3a;padding-bottom:12px}}
 .sub{{color:#8a93a3;font-size:13px;margin-bottom:20px}}
 .card{{background:#1d222c;border:1px solid #2a2f3a;border-radius:10px;padding:14px 16px;margin-bottom:14px}}
 .head{{display:flex;gap:14px;align-items:baseline;flex-wrap:wrap;margin-bottom:8px}}
 .turn{{font-weight:700;color:#f2c14e;font-size:16px}}
 .ts{{color:#7c8698;font-size:12px}}
 .stats{{color:#9db4d0;font-size:13px}}
 .brief{{font-size:15px;line-height:1.6;margin-bottom:10px}}
 .actions{{margin-bottom:8px}}
 .chip{{display:inline-block;background:#263041;border:1px solid #34435c;color:#b8c7dd;border-radius:6px;padding:2px 8px;margin:2px 4px 2px 0;font-size:12px}}
 .res{{display:inline-block;border-radius:6px;padding:2px 8px;margin:2px 4px 2px 0;font-size:11px}}
 .res.ok{{background:#16301f;color:#7fd99a;border:1px solid #27573a}}
 .res.fail{{background:#351c1c;color:#f0a1a1;border:1px solid #6b3434}}
</style></head><body>
<h1>AI 游玩旁白时间轴</h1>
<div class="sub">会话：{session} · 共 {n} 回合</div>
{cards}
</body></html>""".format(session=session_name, n=len(turns), cards="\n".join(cards))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default=None)
    ap.add_argument("--out", default=str(REPO / "timeline.html"))
    args = ap.parse_args()
    base = Path(args.session) if args.session else Path(REPO / "sessions")
    if args.session:
        session_dir = base
    else:
        session_dir = find_newest_session(base)
    turns = load_turns(session_dir)
    if not turns:
        raise SystemExit(f"no turns found in {session_dir}")
    html = render(turns, session_dir.name)
    Path(args.out).write_text(html, encoding="utf-8")
    print(f"wrote {args.out} ({len(turns)} turns) from {session_dir}")


if __name__ == "__main__":
    main()
