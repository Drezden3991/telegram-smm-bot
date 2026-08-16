import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from models.post import Post


POSTS_DATABASE = "posts.db"
POSTS_FILE = "posts.txt"
TXT_MIGRATION_NAME = "posts_txt_to_sqlite_v1"


@dataclass(frozen=True)
class PostsMigrationResult:
    migrated_count: int
    already_migrated: bool
    source_found: bool


def get_connection():
    connection = sqlite3.connect(POSTS_DATABASE)
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
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(posts)")}
    if "telegram_user_id" not in columns:
        connection.execute("ALTER TABLE posts ADD COLUMN telegram_user_id INTEGER")


def initialize_posts_storage():
    with database_connection() as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY, client TEXT NOT NULL, client_context TEXT,
            topic TEXT NOT NULL, style TEXT NOT NULL, text TEXT NOT NULL,
            telegram_user_id INTEGER)""")
        _ensure_owner_column(connection)
        connection.execute("CREATE TABLE IF NOT EXISTS storage_migrations (name TEXT PRIMARY KEY)")


def _post_values(post: Post):
    post_id = post.get("id")
    if not isinstance(post_id, int) or post_id < 1:
        post_id = None
    client_context = post.get("client_context")
    return post_id, str(post.get("client", "")), json.dumps(client_context, ensure_ascii=False) if client_context is not None else None, str(post.get("topic", "")), str(post.get("style", "")), str(post.get("text", ""))


def _post_from_row(row: sqlite3.Row) -> Post:
    return {"id": row["id"], "client": row["client"], "client_context": json.loads(row["client_context"]) if row["client_context"] is not None else None, "topic": row["topic"], "style": row["style"], "text": row["text"]}


def _insert_post(connection: sqlite3.Connection, post: Post, telegram_user_id: int | None) -> int:
    post_id, client, client_context, topic, style, text = _post_values(post)
    if post_id is None:
        cursor = connection.execute("INSERT INTO posts (client, client_context, topic, style, text, telegram_user_id) VALUES (?, ?, ?, ?, ?, ?)", (client, client_context, topic, style, text, telegram_user_id))
        return cursor.lastrowid
    existing = connection.execute(
        "SELECT 1 FROM posts WHERE id = ?", (post_id,)
    ).fetchone()
    if existing is not None:
        cursor = connection.execute(
            "INSERT INTO posts (client, client_context, topic, style, text, telegram_user_id) VALUES (?, ?, ?, ?, ?, ?)",
            (client, client_context, topic, style, text, telegram_user_id),
        )
        return cursor.lastrowid
    connection.execute("INSERT INTO posts (id, client, client_context, topic, style, text, telegram_user_id) VALUES (?, ?, ?, ?, ?, ?, ?)", (post_id, client, client_context, topic, style, text, telegram_user_id))
    return post_id


def load_posts(telegram_user_id: int | None = None) -> list[Post]:
    initialize_posts_storage()
    with database_connection() as connection:
        rows = connection.execute("SELECT * FROM posts WHERE telegram_user_id IS ? ORDER BY id", (telegram_user_id,)).fetchall()
    return [_post_from_row(row) for row in rows]


def save_posts(posts: list[Post], telegram_user_id: int | None = None) -> None:
    """Compatibility helper; it only replaces records of the specified owner."""
    initialize_posts_storage()
    with database_connection() as connection:
        connection.execute("DELETE FROM posts WHERE telegram_user_id IS ?", (telegram_user_id,))
        for post in posts:
            _insert_post(connection, post, telegram_user_id)


def add_post(post: Post, telegram_user_id: int | None = None) -> int:
    initialize_posts_storage()
    with database_connection() as connection:
        return _insert_post(connection, post, telegram_user_id)


def delete_post_by_id(post_id: int, telegram_user_id: int | None = None) -> bool:
    initialize_posts_storage()
    with database_connection() as connection:
        cursor = connection.execute("DELETE FROM posts WHERE id = ? AND telegram_user_id IS ?", (post_id, telegram_user_id))
    return cursor.rowcount == 1


def update_post_by_id(post_id: int, post: Post, telegram_user_id: int | None = None) -> bool:
    _, client, client_context, topic, style, text = _post_values(post)
    initialize_posts_storage()
    with database_connection() as connection:
        cursor = connection.execute("""UPDATE posts SET client = ?, client_context = ?, topic = ?, style = ?, text = ?
            WHERE id = ? AND telegram_user_id IS ?""", (client, client_context, topic, style, text, post_id, telegram_user_id))
    return cursor.rowcount == 1


def assign_legacy_posts(telegram_user_id: int) -> int:
    initialize_posts_storage()
    with database_connection() as connection:
        cursor = connection.execute("UPDATE posts SET telegram_user_id = ? WHERE telegram_user_id IS NULL", (telegram_user_id,))
    return cursor.rowcount


def migrate_posts_from_txt(source_path=None):
    source = Path(source_path or POSTS_FILE)
    source_found = source.exists()
    posts: list[Post] = []
    if source_found:
        data = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(data, list) or not all(isinstance(post, dict) for post in data):
            raise ValueError("posts.txt должен содержать JSON-массив постов.")
        posts = data
    initialize_posts_storage()
    with database_connection() as connection:
        migrated = connection.execute("SELECT 1 FROM storage_migrations WHERE name = ?", (TXT_MIGRATION_NAME,)).fetchone()
        if migrated is not None:
            return PostsMigrationResult(0, True, source_found)
        for post in posts:
            _insert_post(connection, post, None)
        connection.execute("INSERT INTO storage_migrations (name) VALUES (?)", (TXT_MIGRATION_NAME,))
    return PostsMigrationResult(len(posts), False, source_found)
