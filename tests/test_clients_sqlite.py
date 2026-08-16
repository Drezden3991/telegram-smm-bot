import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services import clients as clients_service
from storage import clients as clients_storage


def make_client(
    name="Иван",
    last_name="Иванов",
    phone="+372 5555 0000",
    instagram="@ivan",
    email="ivan@example.com",
    notes="Постоянный клиент",
):
    return {
        "name": name,
        "last_name": last_name,
        "phone": phone,
        "instagram": instagram,
        "email": email,
        "notes": notes,
    }


class ClientsSQLiteTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        temporary_path = Path(self.temporary_directory.name)
        self.database_path = temporary_path / "clients.db"
        self.txt_path = temporary_path / "clients.txt"
        self.database_patch = patch.object(
            clients_storage,
            "CLIENTS_DATABASE",
            str(self.database_path),
        )
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)

    def test_new_database_is_empty_and_reopens_with_saved_clients(self):
        self.assertEqual(clients_storage.load_clients(), [])

        clients_storage.add_client(make_client())

        self.assertEqual(clients_storage.load_clients(), [make_client()])

    def test_records_keep_stable_ids_after_edit_and_delete(self):
        clients_storage.add_client(make_client())
        clients_storage.add_client(make_client(name="Анна", last_name="Петрова"))
        original_records = clients_storage.load_client_records()

        clients_storage.update_client_field_by_full_name(
            "Анна",
            "Петрова",
            "notes",
            "Обновлённые заметки",
        )
        clients_storage.delete_client_by_full_name("Иван", "Иванов")
        clients_storage.add_client(make_client(name="Пётр", last_name="Сидоров"))

        records = clients_storage.load_client_records()
        self.assertEqual(
            [record_id for record_id, _ in records],
            [original_records[1][0], original_records[1][0] + 1],
        )
        self.assertEqual(records[0][1]["notes"], "Обновлённые заметки")

    def test_service_crud_search_and_duplicate_protection_keep_contract(self):
        self.assertEqual(
            clients_service.create_client(make_client()),
            clients_service.CLIENT_CREATED,
        )
        self.assertEqual(
            clients_service.create_client(make_client(name="иван", last_name="ИВАНОВ")),
            clients_service.CLIENT_DUPLICATE,
        )
        self.assertEqual(
            clients_service.search_clients("ВАНОВ"),
            [make_client()],
        )
        status, updated = clients_service.edit_client_field(
            "Иван",
            "Иванов",
            "phone",
            "+372 5555 1111",
        )
        self.assertEqual(status, clients_service.CLIENT_UPDATED)
        self.assertEqual(updated["phone"], "+372 5555 1111")
        self.assertEqual(
            clients_service.delete_client("Иван", "Иванов"),
            clients_service.CLIENT_DELETED,
        )
        self.assertEqual(clients_storage.load_clients(), [])

    def test_migration_is_idempotent_and_leaves_txt_unchanged(self):
        source_text = (
            "  Иван | Иванов | +372 | @ivan | ivan@example.com | Новый формат  \n"
            "\n"
            "Анна | +371 | @anna | anna@example.com | Старый формат\n"
        )
        self.txt_path.write_text(source_text, encoding="utf-8")

        first = clients_storage.migrate_clients_from_txt(self.txt_path)
        second = clients_storage.migrate_clients_from_txt(self.txt_path)

        self.assertEqual(first.migrated_count, 2)
        self.assertFalse(first.already_migrated)
        self.assertTrue(first.source_found)
        self.assertEqual(second.migrated_count, 0)
        self.assertTrue(second.already_migrated)
        self.assertEqual(self.txt_path.read_text(encoding="utf-8"), source_text)
        self.assertEqual(
            clients_storage.load_clients(),
            [
                make_client(
                    phone="+372",
                    instagram="@ivan",
                    notes="Новый формат",
                ),
                make_client(
                    name="Анна",
                    last_name="",
                    phone="+371",
                    instagram="@anna",
                    email="anna@example.com",
                    notes="Старый формат",
                ),
            ],
        )

    def test_migration_of_missing_or_empty_txt_creates_no_clients(self):
        missing = clients_storage.migrate_clients_from_txt(self.txt_path)
        self.assertFalse(missing.source_found)
        self.assertEqual(missing.migrated_count, 0)
        self.assertEqual(clients_storage.load_clients(), [])

        self.database_path.unlink()
        self.txt_path.write_text(" \n\t\n", encoding="utf-8")
        empty = clients_storage.migrate_clients_from_txt(self.txt_path)
        self.assertTrue(empty.source_found)
        self.assertEqual(empty.migrated_count, 0)
        self.assertEqual(clients_storage.load_clients(), [])

    def test_invalid_txt_encoding_does_not_partially_change_database(self):
        clients_storage.add_client(make_client())
        self.txt_path.write_bytes(b"\xff\xfe")

        with self.assertRaises(UnicodeDecodeError):
            clients_storage.migrate_clients_from_txt(self.txt_path)

        self.assertEqual(clients_storage.load_clients(), [make_client()])
