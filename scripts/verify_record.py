"""One-shot: assemble per-turn dataset from an existing save and print summary.

Usage:
    python scripts/verify_record.py --game-root <path> --map Asia [--session-dir out]
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "game_bridge"))

from dump_save import dump_file, default_bridge_dirs  # noqa: E402
from recorder.saves import SaveSet  # noqa: E402
from recorder.turn_logger import load_turn_dataset, build_turns  # noqa: E402
from recorder.session import create_session  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game-root", required=True)
    ap.add_argument("--map", default="Earth")
    ap.add_argument("--session-dir", default="./sessions")
    args = ap.parse_args()

    bridge_dir, work_dir = default_bridge_dirs()
    save_set = SaveSet(args.game_root, args.map)
    tag = save_set.newest_save()
    if not tag:
        print("no save found"); return

    def dump(path, max_depth=8):
        return dump_file(str(path), args.game_root, bridge_dir, work_dir, max_depth)

    stats, periods = load_turn_dataset(dump, save_set, tag)
    for i, p in enumerate(periods):
        if isinstance(p, dict):
            ltc = p.get("lTurnChanges", [])
            itypes = [type(x).__name__ for x in ltc]
            print(f"period[{i}] turns={len(ltc)} elem_types={itypes[:5]}")
            if ltc and isinstance(ltc[0], list):
                elem_types = sorted({type(x).__name__ for x in ltc[0]})
                strs = [x for x in ltc[0] if isinstance(x, str)]
                print(f"  turn0 elems={len(ltc[0])} types={elem_types} strings={strs[:3]}")
    turns = build_turns(stats, periods, meta={"save_tag": tag, "map": args.map})
    print(f"save_tag={tag} turns={len(turns)} periods={len(periods)}")

    sess = create_session(args.session_dir, args.map, tag)
    with open(sess / "turns.jsonl", "w", encoding="utf-8") as f:
        for t in turns:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    with open(sess / "last_turn.json", "w", encoding="utf-8") as f:
        json.dump(turns[-1], f, ensure_ascii=False, indent=1)

    last = turns[-1]
    print(f"session: {sess}")
    print(f"last turn stats (provinces[0:5]): {last['stats']['provinces'][:5]}")
    print(f"last turn changes: {len(last['changes'])} events, sample: {last['changes'][:2]}")


if __name__ == "__main__":
    main()
