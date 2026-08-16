import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


CONTENT_PLANS_DATABASE = "content_plans.db"
CONTENT_PLANS_FILE = "content_plans.txt"
TXT_MIGRATION_NAME = "content_plans_txt_to_sqlite_v1"
SEPARATOR = "-" * 40


@dataclass(frozen=True)
class ContentPlansMigrationResult:
    migrated_count: int
    already_migrated: bool
    source_found: bool


def get_connection():
    connection = sqlite3.connect(CONTENT_PLANS_DATABASE)
    connection.row_factory = sqlite3.Row

    return connection


@contextmanager
def database_connection():
    connection = get_connection()

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_content_plans_storage():
    with database_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS content_plans (
                id INTEGER PRIMARY KEY,
                text TEXT NOT NULL,
                telegram_user_id INTEGER
            )
            """
        )
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(content_plans)"
            )
        }
        if "telegram_user_id" not in columns:
            connection.execute(
                "ALTER TABLE content_plans "
                "ADD COLUMN telegram_user_id INTEGER"
            )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS storage_migrations (
                name TEXT PRIMARY KEY
            )
            """
        )


def _normalize_content_plan(content_plan) -> str:
    return str(content_plan).strip()


def _content_plans_from_text(content: str) -> list[str]:
    normalized_content = content.strip()

    if not normalized_content:
        return []

    return [
        content_plan.strip()
        for content_plan in normalized_content.split(SEPARATOR)
        if content_plan.strip()
    ]


def _read_content_plans_from_txt(source: Path) -> list[str]:
    try:
        content = source.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []

    return _content_plans_from_text(content)


def load_content_plan_records(
    telegram_user_id: int | None = None,
) -> list[dict]:
    initialize_content_plans_storage()

    with database_connection() as connection:
        rows = connection.execute(
            "SELECT id, text FROM content_plans "
            "WHERE telegram_user_id IS ? ORDER BY id",
            (telegram_user_id,),
        ).fetchall()

    return [
        {"id": row["id"], "text": row["text"]}
        for row in rows
    ]


def read_content_plans(
    telegram_user_id: int | None = None,
) -> list[str]:
    return [
        content_plan["text"]
        for content_plan in load_content_plan_records(
            telegram_user_id
        )
    ]


def save_content_plans(
    content_plans,
    telegram_user_id: int | None = None,
) -> None:
    """Compatibility helper for callers from the TXT storage era."""
    prepared_content_plans = [
        _normalize_content_plan(content_plan)
        for content_plan in content_plans
    ]
    initialize_content_plans_storage()

    with database_connection() as connection:
        connection.execute(
            "DELETE FROM content_plans WHERE telegram_user_id IS ?",
            (telegram_user_id,),
        )
        connection.executemany(
            "INSERT INTO content_plans (text, telegram_user_id) "
            "VALUES (?, ?)",
            [
                (content_plan, telegram_user_id)
                for content_plan in prepared_content_plans
            ],
        )


def add_content_plan(
    content_plan,
    telegram_user_id: int | None = None,
) -> int:
    normalized_content_plan = _normalize_content_plan(content_plan)
    initialize_content_plans_storage()

    with database_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO content_plans (text, telegram_user_id) "
            "VALUES (?, ?)",
            (normalized_content_plan, telegram_user_id),
        )

    return cursor.lastrowid


def delete_content_plan_by_position(
    position: int,
    telegram_user_id: int | None = None,
) -> bool:
    records = load_content_plan_records(telegram_user_id)

    if position < 1 or position > len(records):
        return False

    content_plan_id = records[position - 1]["id"]

    with database_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM content_plans "
            "WHERE id = ? AND telegram_user_id IS ?",
            (content_plan_id, telegram_user_id),
        )

    return cursor.rowcount == 1


def update_content_plan_by_position(
    position: int,
    updated_content_plan,
    telegram_user_id: int | None = None,
) -> bool:
    records = load_content_plan_records(telegram_user_id)

    if position < 1 or position > len(records):
        return False

    content_plan_id = records[position - 1]["id"]
    normalized_content_plan = _normalize_content_plan(
        updated_content_plan
    )

    with database_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE content_plans
            SET text = ?
            WHERE id = ? AND telegram_user_id IS ?
            """,
            (
                normalized_content_plan,
                content_plan_id,
                telegram_user_id,
            ),
        )

    return cursor.rowcount == 1


def migrate_content_plans_from_txt(source_path=None):
    source = Path(source_path or CONTENT_PLANS_FILE)
    source_found = source.exists()
    content_plans = _read_content_plans_from_txt(source)
    prepared_content_plans = [
        _normalize_content_plan(content_plan)
        for content_plan in content_plans
    ]

    initialize_content_plans_storage()

    with database_connection() as connection:
        migrated = connection.execute(
            "SELECT 1 FROM storage_migrations WHERE name = ?",
            (TXT_MIGRATION_NAME,),
        ).fetchone()

        if migrated is not None:
            return ContentPlansMigrationResult(
                migrated_count=0,
                already_migrated=True,
                source_found=source_found,
            )

        connection.executemany(
            "INSERT INTO content_plans (text, telegram_user_id) "
            "VALUES (?, NULL)",
            [(content_plan,) for content_plan in prepared_content_plans],
        )
        connection.execute(
            "INSERT INTO storage_migrations (name) VALUES (?)",
            (TXT_MIGRATION_NAME,),
        )

    return ContentPlansMigrationResult(
        migrated_count=len(prepared_content_plans),
        already_migrated=False,
        source_found=source_found,
    )


def assign_legacy_content_plans(telegram_user_id: int) -> int:
    initialize_content_plans_storage()

    with database_connection() as connection:
        cursor = connection.execute(
            "UPDATE content_plans SET telegram_user_id = ? "
            "WHERE telegram_user_id IS NULL",
            (telegram_user_id,),
        )

    return cursor.rowcount
