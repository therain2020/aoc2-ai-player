"""T038: four-way consistency check (SC-009/SC-010 self-audit).

   catalog ops ∪ ACTION_SPEC ∪ EngineGateway implementation ∪ docs/actions.md
   - CRITICAL: ACTION_SPEC action missing from gateway bridge or docs/actions.md
   - WARN    : catalog phase op not in ACTION_SPEC (pending implementation)
   - INFO    : extra gateway/docs names not in ACTION_SPEC

Usage: python scripts/action_closure_check.py [--out docs/action_closure_report.md]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from agent.actions import ACTION_SPEC  # noqa: E402
from agent.mechanics import catalog  # noqa: E402

GATEWAY_SRC = REPO / "game_bridge" / "engine_gateway" / "src"
DOCS_ACTIONS = REPO / "docs" / "actions.md"


def bridge_action_names() -> set[str]:
    """Action-name literals quoted in gateway sources (EngineActions aliases
    `n.equals("camelCase") { n = "snake_case"; }` + handler strings)."""
    names = set()
    for f in GATEWAY_SRC.rglob("*.java"):
        text = f.read_text(encoding="utf-8", errors="replace")
        for m in re.findall(r'"([a-z][a-z0-9_]{3,})"', text):
            names.add(m)
    return names


def doc_action_names() -> set[str]:
    """Actions listed in docs/actions.md table rows (| `name` | ...)."""
    names = set()
    for line in DOCS_ACTIONS.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| ?`(\w+)` ?\|", line)
        if m:
            names.add(m.group(1))
    return names


def catalog_ops() -> set[str]:
    ops = set()
    for e in catalog.MECHANICS.values():
        for p in e.get("phases", []):
            ops.update(p.get("ops", []))
    return ops


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="report file (default: print only)")
    args = ap.parse_args()

    spec = set(ACTION_SPEC)
    ops = catalog_ops()
    bridge = bridge_action_names()
    docnames = doc_action_names()

    lines: list[str] = []
    lines.append("# 动作封闭性自检报告（T038）")
    lines.append(f"- ACTION_SPEC: {len(spec)} 动作")
    lines.append(f"- catalog ops: {len(ops)} 参考操作（含未实现引用）")
    lines.append(f"- gateway 桥实现: {len(bridge & spec)} / {len(spec)} 匹配")
    lines.append(f"- docs/actions.md: {len(docnames)} 动作")

    criticals: list[str] = []
    warns: list[str] = []

    missing_bridge = sorted(spec - bridge)
    if missing_bridge:
        criticals.append(f"CRITICAL: 桥实现缺失 {len(missing_bridge)}: {missing_bridge}")
    missing_docs = sorted(spec - docnames)
    if missing_docs:
        criticals.append(f"CRITICAL: docs/actions.md 缺失 {len(missing_docs)}: {missing_docs}")
    pending_ops = sorted(ops - spec)
    if pending_ops:
        warns.append(f"WARN: catalog 引用但未在 ACTION_SPEC（待实现/仅引导）: {pending_ops}")
    extra_bridge = sorted((bridge - spec) - {"mechanics_catalog"})
    if extra_bridge:
        lines.append(f"- 桥检测到非 ACTION_SPEC 标识符（忽略/过滤）: {extra_bridge[:10]}")

    lines.extend(criticals)
    lines.extend(warns)
    verdict = "CRITICAL" if criticals else ("WARN" if warns else "OK")
    lines.append(f"verdict: {verdict}")

    report = "\n".join(lines)
    print(report)
    if args.out:
        Path(args.out).write_text(report + "\n", encoding="utf-8")
        print(f"report written: {args.out}")
    return 1 if criticals else 0


if __name__ == "__main__":
    sys.exit(main())
