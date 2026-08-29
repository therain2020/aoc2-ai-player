"""Migration diff: legacy bridge /state (from old logs / historical turns.jsonl) vs new gateway /state.

Usage:
    python scripts/state_diff.py --legacy <json file or turn jsonl dir> --live http://127.0.0.1:7187/state
    python scripts/state_diff.py --list                       # list known legacy state samples

Legacy baselines live under _aoc2_analysis (v28_state.json / v29_state.json) or any
sessions/<date>/turns.jsonl "state" column. Output: field-level missing/changed report.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.request

LEGACY_SAMPLES = [
    pathlib.Path.home() / "Downloads" / "_aoc2_analysis" / n
    for n in ("v28_state.json", "v29_state.json")
]

TOP_LEVEL_FIELDS = (
    "turn", "date", "turn_state", "in_game", "money", "provinces", "units",
    "move_points", "tech_points", "messages", "msg_types", "skills", "my_provinces",
    "province_detail", "stability", "treaties", "wars", "front_lines", "neighbors",
    "autosave_in",
)


def load_legacy(path: pathlib.Path) -> dict:
    if path.is_dir():
        recap: dict = {}
        for f in sorted(path.glob("*.jsonl")):
            with f.open(encoding="utf-8") as h:
                for line in h:
                    try:
                        recap.setdefault("state", json.loads(line).get("state"))
                    except Exception:
                        continue
        if recap.get("state"):
            return recap["state"]
        sys.exit(f"[ERROR] no state found in {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "state" in raw:
        raw = raw["state"]
    if not isinstance(raw, dict):
        sys.exit(f"[ERROR] {path} does not contain a state object")
    return raw


def load_live(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def diff(legacy: dict, live: dict) -> dict:
    report: dict = {"missing_in_live": [], "renamed_or_new": [], "type_changed": []}
    dot: dict = {"state": TOP_LEVEL_FIELDS, "neighbors": ["civ_id", "name", "provinces", "armies", "population", "gold", "tech", "relation", "capital", "border_count", "allied", "at_war"]}

    def check(key: str, exp_fields: tuple[str, ...]) -> None:
        lv = legacy.get(key, {}) if isinstance(legacy, dict) else {}
        lo = live.get(key, {}) if isinstance(live, dict) else {}
        if not isinstance(lv, dict) or not isinstance(lo, dict):
            return
        missing = [k for k in exp_fields if k not in lo]
        if missing:
            report["missing_in_live"].append({"section": key, "fields": missing})
        for k in exp_fields:
            if k in lv and k in lo and type(lv[k]).__name__ != type(lo[k]).__name__:
                report["type_changed"].append({"field": f"{key}.{k}", "legacy": type(lv[k]).__name__, "live": type(lo[k]).__name__})

    for key, fields in dot.items():
        check(key, fields)
    extra = sorted(set(live.keys()) - set(TOP_LEVEL_FIELDS))
    if extra:
        report["renamed_or_new"] = extra
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--legacy", type=pathlib.Path, required=True, help="legacy json / jsonl 目录")
    ap.add_argument("--live", default="http://127.0.0.1:7187/state")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if args.list:
        for p in LEGACY_SAMPLES:
            print(f"{p}: {'exists' if p.exists() else 'missing'}")
        return
    r = diff(load_legacy(args.legacy), load_live(args.live))
    print(json.dumps(r, ensure_ascii=False, indent=1))
    fatal = r["missing_in_live"]
    sys.exit(0 if not fatal else 1)


if __name__ == "__main__":
    main()
