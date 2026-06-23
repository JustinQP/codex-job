from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from pathlib import Path
from typing import Callable

from sqlalchemy import Engine, text

from backend.models import utc_now


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    apply: Callable[[Engine], None]


MIGRATIONS: tuple[Migration, ...] = ()


def _utc_iso() -> str:
    return utc_now().astimezone(timezone.utc).isoformat()


def ensure_schema_migrations_table(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                )
                """
            )
        )


def applied_versions(engine: Engine) -> set[str]:
    ensure_schema_migrations_table(engine)
    with engine.begin() as connection:
        rows = connection.execute(text("SELECT version FROM schema_migrations"))
        return {str(row[0]) for row in rows}


def run_migrations(
    engine: Engine,
    *,
    db_path: Path | None = None,
    backup: bool = True,
    migrations: tuple[Migration, ...] = MIGRATIONS,
) -> list[str]:
    del db_path, backup
    ensure_schema_migrations_table(engine)
    completed = applied_versions(engine)
    pending = [migration for migration in migrations if migration.version not in completed]
    applied: list[str] = []
    for migration in pending:
        migration.apply(engine)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO schema_migrations (version, name, applied_at)
                    VALUES (:version, :name, :applied_at)
                    """
                ),
                {
                    "version": migration.version,
                    "name": migration.name,
                    "applied_at": _utc_iso(),
                },
            )
        applied.append(migration.version)
    return applied
