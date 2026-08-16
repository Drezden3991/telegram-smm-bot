import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from scripts import backup_databases
from storage import backups


class SQLiteBackupTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.temporary_path = Path(self.temporary_directory.name)
        self.source = self.temporary_path / "source.db"
        self.backup_directory = self.temporary_path / "backups"
        self.timestamp = datetime(2026, 8, 14, 10, 0, 0, 123456)

    def create_source_database(self, table_name="records"):
        connection = sqlite3.connect(self.source)
        try:
            connection.execute(
                f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY, value TEXT)"
            )
            connection.execute(
                f"INSERT INTO {table_name} (value) VALUES (?)",
                ("temporary test data",),
            )
            connection.commit()
        finally:
            connection.close()

    def test_backup_keeps_source_unchanged_and_contains_same_data(self):
        self.create_source_database()
        source_bytes_before = self.source.read_bytes()

        result = backups.backup_database(
            "records",
            self.source,
            "records",
            self.backup_directory,
            timestamp=self.timestamp,
        )

        self.assertEqual(result.status, "created")
        self.assertEqual(self.source.read_bytes(), source_bytes_before)
        connection = sqlite3.connect(result.backup_path)
        try:
            self.assertEqual(
                connection.execute("SELECT value FROM records").fetchall(),
                [("temporary test data",)],
            )
        finally:
            connection.close()
        backups.verify_sqlite_backup(result.backup_path, "records")

    def test_absent_database_is_skipped_without_creating_database_or_directory(self):
        missing_source = self.temporary_path / "missing.db"

        result = backups.backup_database(
            "missing",
            missing_source,
            "records",
            self.backup_directory,
        )

        self.assertEqual(result.status, "skipped")
        self.assertFalse(missing_source.exists())
        self.assertFalse(self.backup_directory.exists())

    def test_multiple_databases_are_backed_up_separately(self):
        clients_database = self.temporary_path / "clients.db"
        ideas_database = self.temporary_path / "post_ideas.db"
        for database_path, table_name in (
            (clients_database, "clients"),
            (ideas_database, "post_ideas"),
        ):
            connection = sqlite3.connect(database_path)
            try:
                connection.execute(
                    f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY)"
                )
                connection.commit()
            finally:
                connection.close()

        databases = {
            "clients": (lambda: clients_database, "clients"),
            "post_ideas": (lambda: ideas_database, "post_ideas"),
            "posts": (lambda: self.temporary_path / "missing-posts.db", "posts"),
        }
        with patch.object(backups, "DATABASES", databases):
            results = backups.backup_all_databases(
                self.backup_directory,
                timestamp=self.timestamp,
            )

        self.assertEqual(
            [(result.database_name, result.status) for result in results],
            [
                ("clients", "created"),
                ("post_ideas", "created"),
                ("posts", "skipped"),
            ],
        )
        self.assertEqual(len(list(self.backup_directory.glob("*.db"))), 2)

    def test_sequential_backups_do_not_overwrite_each_other(self):
        self.create_source_database()

        first = backups.backup_database(
            "records",
            self.source,
            "records",
            self.backup_directory,
            timestamp=self.timestamp,
        )
        second = backups.backup_database(
            "records",
            self.source,
            "records",
            self.backup_directory,
            timestamp=self.timestamp,
        )

        self.assertNotEqual(first.backup_path, second.backup_path)
        self.assertTrue(first.backup_path.exists())
        self.assertTrue(second.backup_path.exists())

    def test_gitignore_excludes_backup_directory_and_database_files(self):
        gitignore = (Path(__file__).parents[1] / ".gitignore").read_text(
            encoding="utf-8"
        )

        self.assertIn("*.db", gitignore)
        self.assertIn("/backups/", gitignore)

    def test_script_returns_nonzero_when_backup_fails(self):
        with (
            patch.object(
                backup_databases,
                "backup_all_databases",
                side_effect=backups.BackupError("details must stay internal"),
            ),
            patch.object(backup_databases, "load_dotenv"),
            patch.object(backup_databases.os, "chdir"),
            patch.object(backup_databases, "print") as output,
        ):
            result = backup_databases.main()

        self.assertEqual(result, 1)
        self.assertEqual(output.call_args.args[0], "Backup failed: BackupError")
