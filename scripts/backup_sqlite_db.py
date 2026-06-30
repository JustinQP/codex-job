from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "app.db"
DEFAULT_BACKUP_DIR = ROOT_DIR / "data" / "backups"


def backup_database(db_path: Path, backup_dir: Path) -> Path:
    db_path = db_path.expanduser().resolve()
    backup_dir = backup_dir.expanduser().resolve()
    if not db_path.exists():
        raise FileNotFoundError(f"database not found: {db_path}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"{db_path.stem}-{timestamp}{db_path.suffix}"
    shutil.copy2(db_path, backup_path)
    return backup_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up the Codex Job SQLite database.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    args = parser.parse_args()

    backup_path = backup_database(args.db_path, args.backup_dir)
    print(str(backup_path))


if __name__ == "__main__":
    main()
