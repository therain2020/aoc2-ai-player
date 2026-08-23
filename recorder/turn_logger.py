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


def max_turn_from_capitals(capitals_dump) -> int:
    """Absolute turn id from _T dump (max iSinceTurnID across civs)."""
    best = 0
    for civ in capitals_dump.get("lCivsCapitals", []):
        for cap in civ.get("lCapitals", []):
            t = cap.get("iSinceTurnID", 0)
            if t > best:
                best = t
    return best


def load_turn_dataset(dump, save_set: SaveSet, save_tag: str, max_depth: int = 8):
    """Dump _S/_T and all _C_* files; return raw parsed structures.

    _S rows are a sliding window (GRAPH_DATA_LIMIT_PROVINCES=100): row index
    alone cannot define the turn. _T records absolute turn ids (iSinceTurnID)
    and is never truncated, so it anchors absolute turn numbering.
    """
    paths = save_set.paths(save_tag)
    stats = json.loads(dump(str(paths["stats"]), max_depth=max_depth)) if paths["stats"].exists() else {}
    capitals = json.loads(dump(str(paths["capitals"]), max_depth=4)) if paths["capitals"].exists() else {}
    periods = []
    for fp in save_set.turn_change_files(save_tag):
        try:
            periods.append(json.loads(dump(str(fp), max_depth=max_depth)))
        except Exception:
            periods.append(None)
    return stats, capitals, periods


def build_turns(stats, capitals, periods, meta=None):
    """Flatten stats rows + turn-change periods into per-turn dicts."""
    abs_turn = max_turn_from_capitals(capitals)
    num_rows = len(stats.get("lProvinces", []))
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

    num_turns = max(num_rows, len(changes_by_turn))
    for r in range(num_turns):
        row = {}
        for key, attr in STATS_V1.items():
            rows = stats.get(attr, [])
            row[key] = rows[r] if r < len(rows) else []
        changes = changes_by_turn[r] if r < len(changes_by_turn) else []
        # absolute turn: _S window offset +1 (row 0 == absolute turn 1)... via _T anchor
        abs_anchor = abs_turn >= num_rows
        turn_id = r + 1 if abs_anchor or num_rows <= abs_turn + 1 else r
        turn = {
            "turn": turn_id,
            "abs_turn": abs_turn,
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
