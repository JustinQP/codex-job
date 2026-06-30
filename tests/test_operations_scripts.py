from __future__ import annotations

import sqlite3

from scripts.backup_sqlite_db import backup_database
from scripts.cleanup_artifacts import cleanup_artifacts


def test_backup_database_creates_timestamped_copy(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO sample (id) VALUES (1)")
    backup_dir = tmp_path / "backups"

    backup_path = backup_database(db_path, backup_dir)

    assert backup_path.exists()
    with sqlite3.connect(backup_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM sample").fetchone()[0] == 1


def test_cleanup_artifacts_dry_run_and_apply(tmp_path) -> None:
    jobs_dir = tmp_path / "jobs"
    stale_dir = jobs_dir / "1"
    stale_dir.mkdir(parents=True)
    (stale_dir / "run.log").write_text("old", encoding="utf-8")

    dry_run = cleanup_artifacts(jobs_dir, keep_run_ids=set(), apply=False)

    assert dry_run["matched_count"] == 1
    assert dry_run["deleted_count"] == 0
    assert stale_dir.exists()
    applied = cleanup_artifacts(jobs_dir, keep_run_ids=set(), apply=True)

    assert applied["matched_count"] == 1
    assert applied["deleted_count"] == 1
    assert not stale_dir.exists()
