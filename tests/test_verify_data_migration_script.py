from __future__ import annotations

from pathlib import Path
import sqlite3

from scripts.verify_data_migration import verify_migration


def create_legacy_db(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                enabled BOOLEAN NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            );
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY,
                project_id INTEGER NOT NULL,
                prompt TEXT NOT NULL,
                status TEXT NOT NULL,
                timeout_seconds INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            );
            CREATE TABLE app_threads (
                id INTEGER PRIMARY KEY,
                project_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            );
            CREATE TABLE app_turns (
                id INTEGER PRIMARY KEY,
                app_thread_id INTEGER NOT NULL,
                user_message TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL
            );
            INSERT INTO projects (id, name, path, enabled, created_at, updated_at)
            VALUES (1, 'demo', 'E:\\demo', 1, '2026-06-22T00:00:00+00:00', '2026-06-22T00:00:00+00:00');
            INSERT INTO tasks (id, project_id, prompt, status, timeout_seconds, created_at, updated_at)
            VALUES (1, 1, 'hello', 'SUCCESS', 120, '2026-06-22T00:00:00+00:00', '2026-06-22T00:00:00+00:00');
            INSERT INTO app_threads (id, project_id, title, status, created_at, updated_at)
            VALUES (1, 1, 'Chat', 'ACTIVE', '2026-06-22T00:00:00+00:00', '2026-06-22T00:00:00+00:00');
            INSERT INTO app_turns (id, app_thread_id, user_message, status, created_at)
            VALUES (1, 1, 'hi', 'SUCCESS', '2026-06-22T00:00:00+00:00');
            """
        )


def test_verify_migration_runs_on_copy_and_preserves_history_counts(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    output_dir = tmp_path / "verification"
    create_legacy_db(db_path)

    report = verify_migration(db_path=db_path, output_dir=output_dir, agent_command_mode="false")

    assert Path(report["backup_path"]).exists()
    assert Path(report["working_copy"]).exists()
    assert Path(report["report_path"]).exists()
    assert report["source_db"] == str(db_path.resolve())
    assert report["validation"]["history_counts_preserved"] is True
    assert report["validation"]["latest_migration_applied"] is True
    assert report["validation"]["legacy_mode_fallback_expected"] is True
    assert report["validation"]["unbound_project_count"] == 1
    assert report["before"]["counts"]["projects"] == 1
    assert report["after"]["counts"]["projects"] == 1
    assert report["after"]["counts"]["tasks"] == 1
    assert report["after"]["counts"]["app_threads"] == 1
    assert report["after"]["counts"]["app_turns"] == 1
    assert report["after"]["counts"]["workspaces"] == 0
    assert "Copy-Item -Force" in " ".join(report["restore_steps"])

    with sqlite3.connect(db_path) as connection:
        source_columns = {row[1] for row in connection.execute("PRAGMA table_info(projects)")}
    assert "workspace_id" not in source_columns

    with sqlite3.connect(report["working_copy"]) as connection:
        copied_columns = {row[1] for row in connection.execute("PRAGMA table_info(projects)")}
    assert "workspace_id" in copied_columns
