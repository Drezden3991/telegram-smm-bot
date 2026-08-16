"""Check SMM Bot production readiness without starting Telegram polling."""

import asyncio
import os
import sqlite3
import sys
from collections.abc import Mapping
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import main as bot_main
from storage.backups import DATABASES


REQUIRED_ENVIRONMENT = ("TELEGRAM_BOT_TOKEN", "FSM_REDIS_URL")


def check_required_configuration(
    environment: Mapping[str, str],
) -> list[str]:
    return [
        name
        for name in REQUIRED_ENVIRONMENT
        if not environment.get(name)
    ]


def check_sqlite_databases() -> list[str]:
    failures = []

    for database_name, (source_path, expected_table) in DATABASES.items():
        database_path = Path(source_path())
        if not database_path.is_file():
            continue

        connection = None
        try:
            database_uri = f"{database_path.resolve().as_uri()}?mode=ro"
            connection = sqlite3.connect(database_uri, uri=True)
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (expected_table,),
            ).fetchone()
            if integrity != "ok" or table is None:
                failures.append(database_name)
        except sqlite3.DatabaseError:
            failures.append(database_name)
        finally:
            if connection is not None:
                connection.close()

    return failures


async def check_redis(redis_url: str) -> None:
    storage = bot_main.create_fsm_storage(redis_url)
    try:
        await storage.redis.ping()
    finally:
        await storage.close()


async def run_health_check(
    environment: Mapping[str, str] | None = None,
) -> tuple[bool, list[str]]:
    environment = environment if environment is not None else os.environ
    missing_configuration = check_required_configuration(environment)
    if missing_configuration:
        return False, ["required configuration is missing"]

    try:
        await check_redis(environment["FSM_REDIS_URL"])
    except Exception:
        return False, ["Redis FSM backend is unavailable"]

    failed_databases = check_sqlite_databases()
    if failed_databases:
        return False, [
            f"SQLite integrity check failed for: {', '.join(failed_databases)}"
        ]

    return True, ["ready"]


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    os.chdir(PROJECT_ROOT)
    healthy, messages = asyncio.run(run_health_check())

    for message in messages:
        print(f"Health check: {message}")

    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
