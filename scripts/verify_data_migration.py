from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "app.db"

EXPECTED_MAINLINE_TABLES = {
    "agent_command_events",
    "agent_commands",
    "app_threads",
    "app_turns",
    "devices",
    "projects",
    "runs",
    "schema_migrations",
    "turn_events",
    "workspace_execution_locks",
    "workspaces",
}
REMOVED_LEGACY_TABLES = {"tasks", "runner_records"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify that the development database matches the v2.0 mainline reset policy."
    )
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args()

    report = inspect_reset_state(args.db_path)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human_report(report)


def inspect_reset_state(db_path: Path) -> dict[str, Any]:
    db_path = db_path.expanduser().resolve()
    if not db_path.exists():
        return {
            "db_path": str(db_path),
            "exists": False,
            "status": "clean_reset_ready",
            "message": "database does not exist; backend will create a fresh v2.0 schema on startup",
            "legacy_tables_present": [],
            "missing_mainline_tables": sorted(EXPECTED_MAINLINE_TABLES),
        }
    with sqlite3.connect(db_path) as connection:
        tables = table_names(connection)
        legacy_tables = sorted(tables & REMOVED_LEGACY_TABLES)
        missing = sorted(EXPECTED_MAINLINE_TABLES - tables)
        counts = {table: count_rows(connection, table) for table in sorted(tables)}
    status = "ok" if not legacy_tables and not missing else "needs_reset"
    return {
        "db_path": str(db_path),
        "exists": True,
        "status": status,
        "message": (
            "database matches v2.0 mainline schema"
            if status == "ok"
            else "delete data/app.db or clean data before starting a v2.0 development environment"
        ),
        "legacy_tables_present": legacy_tables,
        "missing_mainline_tables": missing,
        "counts": counts,
    }


def table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {str(row[0]) for row in rows}


def count_rows(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def print_human_report(report: dict[str, Any]) -> None:
    print(f"DB: {report['db_path']}")
    print(f"Status: {report['status']}")
    print(report["message"])
    if report["legacy_tables_present"]:
        print(f"Legacy tables present: {', '.join(report['legacy_tables_present'])}")
    if report["missing_mainline_tables"]:
        print(f"Missing mainline tables: {', '.join(report['missing_mainline_tables'])}")


if __name__ == "__main__":
    main()
