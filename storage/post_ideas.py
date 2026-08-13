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


def initialize_post_ideas_storage():
    with database_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS post_ideas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS storage_migrations (
                name TEXT PRIMARY KEY
            )
            """
        )


def load_post_ideas():
    initialize_post_ideas_storage()

    with database_connection() as connection:
        rows = connection.execute(
            "SELECT text FROM post_ideas ORDER BY id"
        ).fetchall()

    return [row["text"] for row in rows]


def load_post_idea_records():
    initialize_post_ideas_storage()

    with database_connection() as connection:
        rows = connection.execute(
            "SELECT id, text FROM post_ideas ORDER BY id"
        ).fetchall()

    return [(row["id"], row["text"]) for row in rows]


def save_all_post_ideas(post_ideas):
    initialize_post_ideas_storage()

    with database_connection() as connection:
        connection.execute("DELETE FROM post_ideas")
        connection.executemany(
            "INSERT INTO post_ideas (text) VALUES (?)",
            [(idea,) for idea in post_ideas],
        )


def add_post_idea_to_file(idea):
    """Compatibility name retained for callers from the TXT storage era."""
    initialize_post_ideas_storage()

    with database_connection() as connection:
        connection.execute(
            "INSERT INTO post_ideas (text) VALUES (?)",
            (idea,),
        )


def add_post_ideas(post_ideas):
    initialize_post_ideas_storage()

    with database_connection() as connection:
        connection.executemany(
            "INSERT INTO post_ideas (text) VALUES (?)",
            [(idea,) for idea in post_ideas],
        )


def update_post_idea_by_position(position, idea):
    initialize_post_ideas_storage()

    with database_connection() as connection:
        row = connection.execute(
            "SELECT id FROM post_ideas ORDER BY id LIMIT 1 OFFSET ?",
            (position - 1,),
        ).fetchone()

        if row is None:
            return False

        connection.execute(
            "UPDATE post_ideas SET text = ? WHERE id = ?",
            (idea, row["id"]),
        )

    return True


def delete_post_idea_by_position(position):
    initialize_post_ideas_storage()

    with database_connection() as connection:
        row = connection.execute(
            "SELECT id FROM post_ideas ORDER BY id LIMIT 1 OFFSET ?",
            (position - 1,),
        ).fetchone()

        if row is None:
            return False

        connection.execute(
            "DELETE FROM post_ideas WHERE id = ?",
            (row["id"],),
        )

    return True


def migrate_post_ideas_from_txt(source_path=None):
    source = Path(source_path or POST_IDEAS_FILE)
    source_found = source.exists()
    ideas = []

    if source_found:
        ideas = [
            line.strip()
            for line in source.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    initialize_post_ideas_storage()

    with database_connection() as connection:
        migrated = connection.execute(
            "SELECT 1 FROM storage_migrations WHERE name = ?",
            (TXT_MIGRATION_NAME,),
        ).fetchone()

        if migrated is not None:
            return PostIdeasMigrationResult(
                migrated_count=0,
                already_migrated=True,
                source_found=source_found,
            )

        connection.executemany(
            "INSERT INTO post_ideas (text) VALUES (?)",
            [(idea,) for idea in ideas],
        )
        connection.execute(
            "INSERT INTO storage_migrations (name) VALUES (?)",
            (TXT_MIGRATION_NAME,),
        )

    return PostIdeasMigrationResult(
        migrated_count=len(ideas),
        already_migrated=False,
        source_found=source_found,
    )
