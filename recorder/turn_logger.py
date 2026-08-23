"""Per-turn state assembly: combine _S stats and _C_* changes into structured turns."""
import json
from pathlib import Path

from recorder.saves import SaveSet, parse_turn_changes

STATS_V1 = {
    "provinces": "lProvinces",
    "population": "lPopulation",
    "rank": "lRank",
    "tech": "lTechnologyLevel",
    "income": "lPlayers_Income",
    "balance": "lPlayers_Balance",
    "mil_spend": "lPlayers_MilitarySpendings",
}


def load_turn_dataset(dump, save_set: SaveSet, save_tag: str, max_depth: int = 8):
    """Dump _S and all _C_* files once; return raw parsed structures."""
    paths = save_set.paths(save_tag)
    stats = json.loads(dump(str(paths["stats"]), max_depth=max_depth)) if paths["stats"].exists() else {}
    periods = []
    for fp in save_set.turn_change_files(save_tag):
        try:
            periods.append(json.loads(dump(str(fp), max_depth=max_depth)))
        except Exception:
            periods.append(None)
    return stats, periods


def build_turns(stats, periods, meta=None):
    """Flatten stats rows + turn-change periods into per-turn dicts."""
    num_turns = len(stats.get("lProvinces", []))
    turns = []
    period_turns = []
    for period in periods:
        if not period:
            period_turns.append([])
            continue
        period_turns.append(period.get("lTurnChanges", []))
    # global turn sequence = concatenation of each period's inner turn lists
    changes_by_turn = []
    for period_turn_list in period_turns:
        for turn_changes in period_turn_list:
            changes_by_turn.append(parse_turn_changes(turn_changes))

    for r in range(max(num_turns, len(changes_by_turn))):
        row = {}
        for key, attr in STATS_V1.items():
            rows = stats.get(attr, [])
            row[key] = rows[r] if r < len(rows) else []
        changes = changes_by_turn[r] if r < len(changes_by_turn) else []
        turn = {
            "turn": r,
            "stats": row,
            "changes": changes,
            "player_civ": None,
            "date": None,
        }
        if meta:
            turn.update(meta)
        turns.append(turn)
    return turns


def write_jsonl(session_dir: Path, turns):
    with open(session_dir / "turns.jsonl", "a", encoding="utf-8") as f:
        for t in turns:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")


def write_turn_file(session_dir, turn):
    with open(session_dir / "turns" / f"turn_{turn['turn']:05d}.json", "w", encoding="utf-8") as f:
        json.dump(turn, f, ensure_ascii=False, indent=1)
