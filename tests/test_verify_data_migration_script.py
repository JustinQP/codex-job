from __future__ import annotations

import sqlite3

from scripts.verify_data_migration import inspect_reset_state


def test_verify_reset_state_reports_missing_database_as_clean_ready(tmp_path) -> None:
    report = inspect_reset_state(tmp_path / "app.db")

    assert report["exists"] is False
    assert report["status"] == "clean_reset_ready"


def test_verify_reset_state_flags_legacy_tables(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY)")
        connection.execute("CREATE TABLE runner_records (runner_id TEXT PRIMARY KEY)")

    report = inspect_reset_state(db_path)

    assert report["status"] == "needs_reset"
    assert report["legacy_tables_present"] == ["runner_records", "tasks"]
