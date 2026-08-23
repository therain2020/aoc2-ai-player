"""Locate and parse AoC2 save files (saves/games/<map>/<saveTag>/...).

Save layout (confirmed from decompiled source):
    saves/games/<map>/
        Age_of_Civilizations        : "saveTag;" entries
        <saveTag>/
            TS/<saveTag>_O         : initial owner per province
            TS/<saveTag>_T         : capital timeline
            TS/<saveTag>_S         : per-turn stats (List per turn, per civ)
            TS/TURN/<saveTag>_C_<p>: turn changes for save-period p (nested per turn)
            TS/TURN/Age_of_Civilizations : period counter text
"""
from pathlib import Path

SCHEMA_DIR = "saves"


class SaveSet:
    def __init__(self, game_root, map_name):
        self.game_root = Path(game_root)
        self.map_name = map_name
        self.base = self.game_root / SCHEMA_DIR / "games" / map_name

    def list_saves(self):
        manifest = self.base / "Age_of_Civilizations"
        if not manifest.exists():
            return []
        return [t for t in manifest.read_text(encoding="utf-8", errors="replace").split(";") if t]

    def newest_save(self):
        tags = self.list_saves()
        if not tags:
            return None
        return tags[-1]

    def paths(self, save_tag):
        base = self.base / save_tag
        return {
            "stats": base / "TS" / f"{save_tag}_S",
            "owners": base / "TS" / f"{save_tag}_O",
            "capitals": base / "TS" / f"{save_tag}_T",
            "turns": base / "TS" / "TURN",
            "turn_counter": base / "TS" / "TURN" / "Age_of_Civilizations",
        }

    def turn_change_files(self, save_tag):
        turns_dir = self.paths(save_tag)["turns"]
        if not turns_dir.exists():
            return []
        files = sorted(
            (p for p in turns_dir.glob(f"{save_tag}_C_*") if p.is_file() and "BACKUP" not in p.name),
            key=lambda p: int(p.name.rsplit("_", 1)[-1]),
        )
        return files

    def player_stat_civ_tags(self):
        stats_dir = self.game_root / SCHEMA_DIR / "stats" / "civ"
        if not stats_dir.exists():
            return []
        return [p for p in stats_dir.iterdir() if p.is_file() and not p.name.startswith("Age_of")]


def parse_turn_changes(turn_changes):
    """Normalize one turn's change list (list of {iProvinceID, iToCivID, isOccupied})."""
    events = []
    for ch in turn_changes:
        events.append({
            "province_id": ch.get("iProvinceID"),
            "to_civ": ch.get("iToCivID"),
            "occupied": bool(ch.get("isOccupied", False)),
        })
    return events


def parse_stats_dump(dumped, fields):
    """_S dumped JSON -> {field: [per-turn list of per-civ values]} for selected fields."""
    out = {}
    for key, attr in fields:
        rows = dumped.get(attr, [])
        out[key] = rows
    return out
