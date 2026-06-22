from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import create_engine

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.migrations import MIGRATIONS, run_migrations


DEFAULT_DB_PATH = ROOT_DIR / "data" / "app.db"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "data" / "migration-verification"


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify codex-job data migration on a SQLite copy.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--agent-command-mode", choices=["true", "false"], default="false")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args()

    report = verify_migration(
        db_path=args.db_path,
        output_dir=args.output_dir,
        agent_command_mode=args.agent_command_mode,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print_human_report(report)


def verify_migration(*, db_path: Path, output_dir: Path, agent_command_mode: str = "false") -> dict[str, Any]:
    source = db_path.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"database not found: {source}")
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    backup_path = output_dir / f"{source.name}.backup-{stamp}"
    working_path = output_dir / f"{source.stem}.migration-copy-{stamp}{source.suffix}"
    shutil.copy2(source, backup_path)
    shutil.copy2(source, working_path)

    before = inspect_database(source)
    engine = create_engine(
        f"sqlite:///{working_path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    applied = run_migrations(engine, db_path=working_path, backup=False)
    engine.dispose()
    after = inspect_database(working_path)
    validation = validate_report(before, after, agent_command_mode=agent_command_mode)
    report = {
        "source_db": str(source),
        "backup_path": str(backup_path),
        "working_copy": str(working_path),
        "agent_command_mode": agent_command_mode,
        "applied_migrations": applied,
        "latest_migration": MIGRATIONS[-1].version,
        "before": before,
        "after": after,
        "validation": validation,
        "restore_steps": [
            "Stop backend and agents.",
            f"Copy backup over source: Copy-Item -Force '{backup_path}' '{source}'",
            "Start backend with AGENT_COMMAND_MODE=false to verify legacy runner fallback.",
        ],
    }
    report_path = output_dir / f"migration-report-{stamp}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["report_path"] = str(report_path)
    return report


def inspect_database(db_path: Path) -> dict[str, Any]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        tables = table_names(connection)
        counts = {table: count_rows(connection, table) for table in tables}
        project_rows = fetch_rows(
            connection,
            "projects",
            ["id", "name", "path", "workspace_id", "workspace_binding_status"],
        )
        workspace_rows = fetch_rows(
            connection,
            "workspaces",
            ["id", "device_id", "workspace_key", "name", "path_label", "enabled"],
        )
        device_rows = fetch_rows(
            connection,
            "devices",
            ["device_id", "display_name", "status", "last_heartbeat_at"],
        )
        return {
            "tables": sorted(tables),
            "counts": {
                "projects": counts.get("projects", 0),
                "workspaces": counts.get("workspaces", 0),
                "devices": counts.get("devices", 0),
                "tasks": counts.get("tasks", 0),
                "app_threads": counts.get("app_threads", 0),
                "app_turns": counts.get("app_turns", 0),
            },
            "all_counts": counts,
            "projects": project_rows,
            "workspaces": workspace_rows,
            "devices": device_rows,
            "schema_migrations": fetch_rows(connection, "schema_migrations", ["version", "name", "applied_at"]),
        }


def table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {str(row[0]) for row in rows}


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    if table not in table_names(connection):
        return set()
    return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({quote_identifier(table)})")}


def count_rows(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {quote_identifier(table)}").fetchone()[0])


def fetch_rows(connection: sqlite3.Connection, table: str, columns: list[str]) -> list[dict[str, Any]]:
    if table not in table_names(connection):
        return []
    available = table_columns(connection, table)
    selected = [column for column in columns if column in available]
    if not selected:
        return []
    sql = f"SELECT {', '.join(quote_identifier(column) for column in selected)} FROM {quote_identifier(table)} ORDER BY 1"
    return [dict(row) for row in connection.execute(sql).fetchall()]


def validate_report(before: dict[str, Any], after: dict[str, Any], *, agent_command_mode: str) -> dict[str, Any]:
    preserved_tables = ["projects", "tasks", "app_threads", "app_turns"]
    count_matches = {
        table: before["counts"].get(table, 0) == after["counts"].get(table, 0)
        for table in preserved_tables
    }
    unbound_projects = [
        project
        for project in after["projects"]
        if not project.get("workspace_id") or project.get("workspace_binding_status") in {None, "UNBOUND"}
    ]
    latest_applied = any(
        row.get("version") == MIGRATIONS[-1].version
        for row in after.get("schema_migrations", [])
    )
    return {
        "history_counts_preserved": all(count_matches.values()),
        "count_matches": count_matches,
        "latest_migration_applied": latest_applied,
        "legacy_mode_fallback_expected": agent_command_mode == "false",
        "unbound_project_count": len(unbound_projects),
        "unbound_projects": unbound_projects,
        "old_tables_preserved": all(table in after["tables"] for table in preserved_tables),
    }


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def print_human_report(report: dict[str, Any]) -> None:
    print(f"Source DB: {report['source_db']}")
    print(f"Backup: {report['backup_path']}")
    print(f"Working copy: {report['working_copy']}")
    print(f"Report: {report['report_path']}")
    print(f"Applied migrations: {', '.join(report['applied_migrations']) or 'none'}")
    print(f"Latest migration: {report['latest_migration']}")
    print("Counts before -> after:")
    for key, before_count in report["before"]["counts"].items():
        print(f"  {key}: {before_count} -> {report['after']['counts'].get(key, 0)}")
    print(f"Unbound projects: {report['validation']['unbound_project_count']}")
    print("Restore:")
    for step in report["restore_steps"]:
        print(f"  - {step}")


if __name__ == "__main__":
    main()
