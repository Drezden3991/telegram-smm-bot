import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


POST_IDEAS_DATABASE = "post_ideas.db"
POST_IDEAS_FILE = "post_ideas.txt"
TXT_MIGRATION_NAME = "post_ideas_txt_to_sqlite_v1"


@dataclass(frozen=True)
class PostIdeasMigrationResult:
    migrated_count: int
    already_migrated: bool
    source_found: bool


def get_connection():
    connection = sqlite3.connect(POST_IDEAS_DATABASE)
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


def _ensure_owner_column(connection: sqlite3.Connection) -> None:
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(post_ideas)")}
    if "telegram_user_id" not in columns:
        connection.execute("ALTER TABLE post_ideas ADD COLUMN telegram_user_id INTEGER")


def initialize_post_ideas_storage():
    with database_connection() as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS post_ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL, telegram_user_id INTEGER)""")
        _ensure_owner_column(connection)
        connection.execute("CREATE TABLE IF NOT EXISTS storage_migrations (name TEXT PRIMARY KEY)")


def load_post_ideas(telegram_user_id: int | None = None) -> list[str]:
    initialize_post_ideas_storage()
    with database_connection() as connection:
        rows = connection.execute("SELECT text FROM post_ideas WHERE telegram_user_id IS ? ORDER BY id", (telegram_user_id,)).fetchall()
    return [row["text"] for row in rows]


def load_post_idea_records(telegram_user_id: int | None = None) -> list[tuple[int, str]]:
    initialize_post_ideas_storage()
    with database_connection() as connection:
        rows = connection.execute("SELECT id, text FROM post_ideas WHERE telegram_user_id IS ? ORDER BY id", (telegram_user_id,)).fetchall()
    return [(row["id"], row["text"]) for row in rows]


def save_all_post_ideas(post_ideas, telegram_user_id: int | None = None):
    initialize_post_ideas_storage()
    with database_connection() as connection:
        connection.execute("DELETE FROM post_ideas WHERE telegram_user_id IS ?", (telegram_user_id,))
        connection.executemany("INSERT INTO post_ideas (text, telegram_user_id) VALUES (?, ?)", [(idea, telegram_user_id) for idea in post_ideas])


def add_post_idea_to_file(idea, telegram_user_id: int | None = None) -> int:
    """Compatibility name retained for callers from the TXT storage era."""
    initialize_post_ideas_storage()
    with database_connection() as connection:
        cursor = connection.execute("INSERT INTO post_ideas (text, telegram_user_id) VALUES (?, ?)", (idea, telegram_user_id))
    return cursor.lastrowid


def add_post_ideas(post_ideas, telegram_user_id: int | None = None):
    initialize_post_ideas_storage()
    with database_connection() as connection:
        connection.executemany("INSERT INTO post_ideas (text, telegram_user_id) VALUES (?, ?)", [(idea, telegram_user_id) for idea in post_ideas])


def _record_id_at_position(connection: sqlite3.Connection, position: int, telegram_user_id: int | None):
    if position < 1:
        return None
    row = connection.execute("SELECT id FROM post_ideas WHERE telegram_user_id IS ? ORDER BY id LIMIT 1 OFFSET ?", (telegram_user_id, position - 1)).fetchone()
    return row["id"] if row else None


def update_post_idea_by_position(position, idea, telegram_user_id: int | None = None):
    initialize_post_ideas_storage()
    with database_connection() as connection:
        record_id = _record_id_at_position(connection, position, telegram_user_id)
        if record_id is None:
            return False
        cursor = connection.execute("UPDATE post_ideas SET text = ? WHERE id = ? AND telegram_user_id IS ?", (idea, record_id, telegram_user_id))
    return cursor.rowcount == 1


def delete_post_idea_by_position(position, telegram_user_id: int | None = None):
    initialize_post_ideas_storage()
    with database_connection() as connection:
        record_id = _record_id_at_position(connection, position, telegram_user_id)
        if record_id is None:
            return False
        cursor = connection.execute("DELETE FROM post_ideas WHERE id = ? AND telegram_user_id IS ?", (record_id, telegram_user_id))
    return cursor.rowcount == 1


def assign_legacy_post_ideas(telegram_user_id: int) -> int:
    initialize_post_ideas_storage()
    with database_connection() as connection:
        cursor = connection.execute("UPDATE post_ideas SET telegram_user_id = ? WHERE telegram_user_id IS NULL", (telegram_user_id,))
    return cursor.rowcount


def migrate_post_ideas_from_txt(source_path=None):
    source = Path(source_path or POST_IDEAS_FILE)
    source_found = source.exists()
    ideas = [line.strip() for line in source.read_text(encoding="utf-8").splitlines() if line.strip()] if source_found else []
    initialize_post_ideas_storage()
    with database_connection() as connection:
        migrated = connection.execute("SELECT 1 FROM storage_migrations WHERE name = ?", (TXT_MIGRATION_NAME,)).fetchone()
        if migrated is not None:
            return PostIdeasMigrationResult(0, True, source_found)
        connection.executemany("INSERT INTO post_ideas (text, telegram_user_id) VALUES (?, NULL)", [(idea,) for idea in ideas])
        connection.execute("INSERT INTO storage_migrations (name) VALUES (?)", (TXT_MIGRATION_NAME,))
    return PostIdeasMigrationResult(len(ideas), False, source_found)
