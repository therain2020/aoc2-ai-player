"""M1 recorder: poll saves, assemble per-turn data, write JSONL + screenshots.

Usage: python -m recorder.main --game-root <path> --map <Earth>
"""
import argparse
import time

from recorder import session
from recorder.saves import SaveSet
from recorder.turn_logger import load_turn_dataset, build_turns, write_jsonl, write_turn_file, max_turn_from_capitals
from recorder.screenshots import find_window, capture


def poll_loop(game_root, map_name, session_dir, screenshot=False, poll_sec=1.0):
    import sys
    repo_root = __import__("pathlib").Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "game_bridge"))
    from dump_save import dump_file, default_bridge_dirs

    bridge_dir, work_dir = default_bridge_dirs()

    def dump(path, max_depth=8):
        return dump_file(str(path), game_root, bridge_dir, work_dir, max_depth)

    save_set = SaveSet(game_root, map_name)
    state = {"tag": None, "abs_turn": -1, "session": None}

    while True:
        tag = save_set.newest_save()
        if not tag:
            time.sleep(poll_sec)
            continue
        try:
            stats, capitals, periods = load_turn_dataset(dump, save_set, tag)
            abs_turn = max_turn_from_capitals(capitals)
        except Exception as e:
            print(f"dump failed: {e}")
            time.sleep(poll_sec)
            continue

        if tag != state["tag"]:
            state["tag"] = tag
            state["abs_turn"] = -1
            state["session"] = session.create_session(session_dir, map_name, tag)
            print(f"new save {tag} -> session {state['session']}")

        if abs_turn > state["abs_turn"]:
            turns = build_turns(stats, capitals, periods, meta={"save_tag": tag, "map": map_name})
            new_turns = [t for t in turns if t["turn"] > state["abs_turn"]]
            if new_turns:
                write_jsonl(state["session"], new_turns)
                for t in new_turns:
                    write_turn_file(state["session"], t)
                    print(f"turn {t['turn']}: changes={len(t['changes'])}")
            if screenshot:
                hwnd = find_window("Age of Civilizations II")
                if hwnd:
                    try:
                        capture(hwnd, state["session"] / "turns" / f"turn_{abs_turn:05d}.png")
                    except Exception as e:
                        print(f"screenshot failed: {e}")
            state["abs_turn"] = abs_turn
        time.sleep(poll_sec)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game-root", required=True)
    ap.add_argument("--map", default="Earth")
    ap.add_argument("--session-dir", default="./sessions")
    ap.add_argument("--screenshot", action="store_true")
    ap.add_argument("--poll-sec", type=float, default=1.0)
    args = ap.parse_args()
    poll_loop(args.game_root, args.map, args.session_dir, args.screenshot, args.poll_sec)


if __name__ == "__main__":
    main()
