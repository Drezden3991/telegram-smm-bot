import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from models.client import Client


CLIENTS_DATABASE = "clients.db"
CLIENTS_FILE = "clients.txt"
CLIENT_FIELD_SEPARATOR = " | "
TXT_MIGRATION_NAME = "clients_txt_to_sqlite_v1"


@dataclass(frozen=True)
class ClientsMigrationResult:
    migrated_count: int
    already_migrated: bool
    source_found: bool


def create_client_from_line(line: str) -> Client:
    parts = line.split(CLIENT_FIELD_SEPARATOR)
    if len(parts) == 6:
        return dict(zip(("name", "last_name", "phone", "instagram", "email", "notes"), parts))
    if len(parts) == 5:
        return {"name": parts[0], "last_name": "", "phone": parts[1], "instagram": parts[2], "email": parts[3], "notes": parts[4]}
    return {"name": line, "last_name": "", "phone": "", "instagram": "", "email": "", "notes": ""}


def create_line_from_client(client: Client) -> str:
    return CLIENT_FIELD_SEPARATOR.join(client[key] for key in ("name", "last_name", "phone", "instagram", "email", "notes"))


def get_connection():
    connection = sqlite3.connect(CLIENTS_DATABASE)
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
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(clients)")}
    if "telegram_user_id" not in columns:
        connection.execute("ALTER TABLE clients ADD COLUMN telegram_user_id INTEGER")


def initialize_clients_storage():
    with database_connection() as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, last_name TEXT NOT NULL,
            phone TEXT NOT NULL, instagram TEXT NOT NULL, email TEXT NOT NULL, notes TEXT NOT NULL,
            telegram_user_id INTEGER)""")
        _ensure_owner_column(connection)
        connection.execute("CREATE TABLE IF NOT EXISTS storage_migrations (name TEXT PRIMARY KEY)")


def _client_from_row(row: sqlite3.Row) -> Client:
    return {key: row[key] for key in ("name", "last_name", "phone", "instagram", "email", "notes")}


def load_clients(telegram_user_id: int | None = None) -> list[Client]:
    initialize_clients_storage()
    with database_connection() as connection:
        rows = connection.execute("SELECT * FROM clients WHERE telegram_user_id IS ? ORDER BY id", (telegram_user_id,)).fetchall()
    return [_client_from_row(row) for row in rows]


def load_client_records(telegram_user_id: int | None = None) -> list[tuple[int, Client]]:
    initialize_clients_storage()
    with database_connection() as connection:
        rows = connection.execute("SELECT * FROM clients WHERE telegram_user_id IS ? ORDER BY id", (telegram_user_id,)).fetchall()
    return [(row["id"], _client_from_row(row)) for row in rows]


def save_clients(clients: list[Client], telegram_user_id: int | None = None) -> None:
    """Compatibility helper; it only replaces records of the specified owner."""
    initialize_clients_storage()
    with database_connection() as connection:
        connection.execute("DELETE FROM clients WHERE telegram_user_id IS ?", (telegram_user_id,))
        connection.executemany("""INSERT INTO clients (name, last_name, phone, instagram, email, notes, telegram_user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)""", [(client["name"], client["last_name"], client["phone"], client["instagram"], client["email"], client["notes"], telegram_user_id) for client in clients])


def add_client(client: Client, telegram_user_id: int | None = None) -> int:
    initialize_clients_storage()
    with database_connection() as connection:
        cursor = connection.execute("""INSERT INTO clients (name, last_name, phone, instagram, email, notes, telegram_user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)""", (client["name"], client["last_name"], client["phone"], client["instagram"], client["email"], client["notes"], telegram_user_id))
    return cursor.lastrowid


def delete_client_by_full_name(name: str, last_name: str, telegram_user_id: int | None = None) -> bool:
    initialize_clients_storage()
    with database_connection() as connection:
        row = connection.execute("""SELECT id FROM clients WHERE lower(name) = lower(?) AND lower(last_name) = lower(?)
            AND telegram_user_id IS ? ORDER BY id LIMIT 1""", (name, last_name, telegram_user_id)).fetchone()
        if row is None:
            return False
        connection.execute("DELETE FROM clients WHERE id = ? AND telegram_user_id IS ?", (row["id"], telegram_user_id))
    return True


def update_client_field_by_full_name(name: str, last_name: str, field_key: str, new_value: str, telegram_user_id: int | None = None) -> bool:
    if field_key not in {"name", "last_name", "phone", "instagram", "email", "notes"}:
        return False
    initialize_clients_storage()
    with database_connection() as connection:
        row = connection.execute("""SELECT id FROM clients WHERE lower(name) = lower(?) AND lower(last_name) = lower(?)
            AND telegram_user_id IS ? ORDER BY id LIMIT 1""", (name, last_name, telegram_user_id)).fetchone()
        if row is None:
            return False
        cursor = connection.execute(f"UPDATE clients SET {field_key} = ? WHERE id = ? AND telegram_user_id IS ?", (new_value, row["id"], telegram_user_id))
    return cursor.rowcount == 1


def assign_legacy_clients(telegram_user_id: int) -> int:
    initialize_clients_storage()
    with database_connection() as connection:
        cursor = connection.execute("UPDATE clients SET telegram_user_id = ? WHERE telegram_user_id IS NULL", (telegram_user_id,))
    return cursor.rowcount


def migrate_clients_from_txt(source_path=None):
    source = Path(source_path or CLIENTS_FILE)
    source_found = source.exists()
    clients = [create_client_from_line(line.strip()) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()] if source_found else []
    initialize_clients_storage()
    with database_connection() as connection:
        migrated = connection.execute("SELECT 1 FROM storage_migrations WHERE name = ?", (TXT_MIGRATION_NAME,)).fetchone()
        if migrated is not None:
            return ClientsMigrationResult(0, True, source_found)
        connection.executemany("""INSERT INTO clients (name, last_name, phone, instagram, email, notes, telegram_user_id)
            VALUES (?, ?, ?, ?, ?, ?, NULL)""", [(c["name"], c["last_name"], c["phone"], c["instagram"], c["email"], c["notes"]) for c in clients])
        connection.execute("INSERT INTO storage_migrations (name) VALUES (?)", (TXT_MIGRATION_NAME,))
    return ClientsMigrationResult(len(clients), False, source_found)
