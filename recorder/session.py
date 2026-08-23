"""Session directory management (per recorded game run)."""
import json
import os
from datetime import datetime
from pathlib import Path


def create_session(base_dir: str, map_name: str, save_tag: str) -> Path:
    session_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    session_dir = Path(base_dir) / f"{session_id}-{map_name}-{save_tag[:8]}"
    (session_dir / "turns").mkdir(parents=True, exist_ok=True)
    meta = {
        "session_id": session_id,
        "created": datetime.now().isoformat(),
        "map": map_name,
        "save_tag": save_tag,
    }
    with open(session_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return session_dir
