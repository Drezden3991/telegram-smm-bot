"""Explicit, local SQLite backups for SMM Bot user-data databases."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from storage import clients, content_plans, post_ideas, posts


DEFAULT_BACKUP_DIRECTORY = "backups"
DATABASES = {
    "clients": (lambda: clients.CLIENTS_DATABASE, "clients"),
    "post_ideas": (lambda: post_ideas.POST_IDEAS_DATABASE, "post_ideas"),
    "posts": (lambda: posts.POSTS_DATABASE, "posts"),
    "content_plans": (lambda: content_plans.CONTENT_PLANS_DATABASE, "content_plans"),
}


class BackupError(RuntimeError):
    """Raised when a backup cannot be safely completed or verified."""


@dataclass(frozen=True)
class BackupResult:
    database_name: str
    status: str
    backup_path: Path | None = None


def _backup_filename(database_name: str, timestamp: datetime | None = None) -> str:
    timestamp = timestamp or datetime.now()
    return f"{database_name}_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.db"


def _next_backup_path(
    database_name: str,
    backup_directory: Path,
    timestamp: datetime | None,
) -> Path:
    base_path = backup_directory / _backup_filename(database_name, timestamp)
    if not base_path.exists():
        return base_path

    suffix = 2
    while True:
        candidate = base_path.with_stem(f"{base_path.stem}_{suffix}")
        if not candidate.exists():
            return candidate
        suffix += 1


def verify_sqlite_backup(backup_path: Path, expected_table: str) -> None:
    connection = sqlite3.connect(backup_path)
    try:
        integrity_result = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity_result != "ok":
            raise BackupError("SQLite backup integrity check failed.")

        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (expected_table,),
        ).fetchone()
        if table is None:
            raise BackupError("SQLite backup is missing its expected table.")
    finally:
        connection.close()


def backup_database(
    database_name: str,
    source_path: str | Path,
    expected_table: str,
    backup_directory: str | Path,
    *,
    timestamp: datetime | None = None,
) -> BackupResult:
    source = Path(source_path)
    if not source.is_file():
        return BackupResult(database_name, "skipped")

    target_directory = Path(backup_directory)
    target_directory.mkdir(parents=True, exist_ok=True)
    backup_path = _next_backup_path(
        database_name,
        target_directory,
        timestamp,
    )

    try:
        source_uri = f"{source.resolve().as_uri()}?mode=ro"
        source_connection = sqlite3.connect(source_uri, uri=True)
        backup_connection = sqlite3.connect(backup_path)
        try:
            source_connection.backup(backup_connection)
        finally:
            backup_connection.close()
            source_connection.close()
        verify_sqlite_backup(backup_path, expected_table)
    except Exception as error:
        if backup_path.exists():
            backup_path.unlink()
        if isinstance(error, BackupError):
            raise
        raise BackupError("SQLite backup failed.") from error

    return BackupResult(database_name, "created", backup_path)


def backup_all_databases(
    backup_directory: str | Path = DEFAULT_BACKUP_DIRECTORY,
    *,
    timestamp: datetime | None = None,
) -> list[BackupResult]:
    return [
        backup_database(
            database_name,
            source_path(),
            expected_table,
            backup_directory,
            timestamp=timestamp,
        )
        for database_name, (source_path, expected_table) in DATABASES.items()
    ]
