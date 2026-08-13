import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services import post_ideas as post_ideas_service
from storage import post_ideas as post_ideas_storage


class PostIdeasSQLiteTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        temporary_path = Path(self.temporary_directory.name)
        self.database_path = temporary_path / "post_ideas.db"
        self.txt_path = temporary_path / "post_ideas.txt"
        self.database_patch = patch.object(
            post_ideas_storage,
            "POST_IDEAS_DATABASE",
            str(self.database_path),
        )
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)

    def test_new_database_is_empty_and_reopens_with_saved_records(self):
        self.assertEqual(post_ideas_storage.load_post_ideas(), [])

        post_ideas_storage.add_post_idea_to_file("💡 Первая идея")
        self.assertEqual(
            post_ideas_storage.load_post_ideas(),
            ["💡 Первая идея"],
        )

    def test_records_have_stable_database_ids(self):
        post_ideas_storage.add_post_ideas(
            ["💡 Первая идея", "💡 Вторая идея"]
        )
        original_records = post_ideas_storage.load_post_idea_records()

        post_ideas_storage.update_post_idea_by_position(
            2,
            "💡 Обновлённая идея",
        )
        post_ideas_storage.delete_post_idea_by_position(1)
        post_ideas_storage.add_post_idea_to_file("💡 Третья идея")

        self.assertEqual(
            post_ideas_storage.load_post_idea_records(),
            [
                (original_records[1][0], "💡 Обновлённая идея"),
                (original_records[1][0] + 1, "💡 Третья идея"),
            ],
        )

    def test_service_add_edit_delete_search_and_random_keep_contract(self):
        status, added = post_ideas_service.create_post_idea(
            "Первая идея"
        )
        self.assertEqual(status, post_ideas_service.IDEA_OPERATION_READY)
        self.assertEqual(added, "💡 Первая идея")

        duplicate_status, _ = post_ideas_service.create_post_idea(
            "ПЕРВАЯ ИДЕЯ"
        )
        self.assertEqual(
            duplicate_status,
            post_ideas_service.IDEA_DUPLICATE,
        )

        post_ideas_storage.add_post_idea_to_file("💡 Вторая идея")
        ideas = post_ideas_storage.load_post_ideas()
        self.assertEqual(
            post_ideas_service.find_post_ideas(ideas, "ВТОРАЯ"),
            [(2, "💡 Вторая идея")],
        )
        self.assertIn(
            post_ideas_service.choose_random_post_idea(ideas),
            ideas,
        )

        edit_status, edited, _ = post_ideas_service.edit_post_idea(
            2,
            "💡 Вторая идея",
            "Обновлённая идея",
        )
        self.assertEqual(edit_status, post_ideas_service.IDEA_OPERATION_READY)
        self.assertEqual(edited, "💡 Обновлённая идея")

        delete_status, deleted, remaining = (
            post_ideas_service.delete_post_idea(
                "1",
                post_ideas_storage.load_post_ideas(),
            )
        )
        self.assertEqual(delete_status, post_ideas_service.IDEA_OPERATION_READY)
        self.assertEqual(deleted, "💡 Первая идея")
        self.assertEqual(remaining, ["💡 Обновлённая идея"])

    def test_ai_batch_save_adds_only_new_ideas_once(self):
        post_ideas_storage.add_post_idea_to_file("💡 Существующая идея")

        added, duplicates = post_ideas_service.save_selected_post_ideas(
            ["Новая идея", "существующая ИДЕЯ", "Ещё одна идея"]
        )

        self.assertEqual(
            added,
            ["💡 Новая идея", "💡 Ещё одна идея"],
        )
        self.assertEqual(duplicates, ["💡 существующая ИДЕЯ"])
        self.assertEqual(
            post_ideas_storage.load_post_ideas(),
            [
                "💡 Существующая идея",
                "💡 Новая идея",
                "💡 Ещё одна идея",
            ],
        )

    def test_migration_is_idempotent_and_leaves_txt_unchanged(self):
        source_text = "  💡 Первая идея  \n\nВторая идея\n"
        self.txt_path.write_text(source_text, encoding="utf-8")

        first_result = post_ideas_storage.migrate_post_ideas_from_txt(
            self.txt_path
        )
        second_result = post_ideas_storage.migrate_post_ideas_from_txt(
            self.txt_path
        )

        self.assertEqual(first_result.migrated_count, 2)
        self.assertFalse(first_result.already_migrated)
        self.assertTrue(first_result.source_found)
        self.assertEqual(second_result.migrated_count, 0)
        self.assertTrue(second_result.already_migrated)
        self.assertEqual(
            self.txt_path.read_text(encoding="utf-8"),
            source_text,
        )
        self.assertEqual(
            post_ideas_storage.load_post_ideas(),
            ["💡 Первая идея", "Вторая идея"],
        )

    def test_migration_of_missing_or_empty_txt_creates_no_records(self):
        result = post_ideas_storage.migrate_post_ideas_from_txt(
            self.txt_path
        )

        self.assertFalse(result.source_found)
        self.assertEqual(result.migrated_count, 0)
        self.assertEqual(post_ideas_storage.load_post_ideas(), [])

    def test_migration_of_empty_txt_creates_no_records(self):
        self.txt_path.write_text("  \n\t\n", encoding="utf-8")

        result = post_ideas_storage.migrate_post_ideas_from_txt(
            self.txt_path
        )

        self.assertTrue(result.source_found)
        self.assertEqual(result.migrated_count, 0)
        self.assertEqual(post_ideas_storage.load_post_ideas(), [])

    def test_invalid_txt_encoding_does_not_partially_change_database(self):
        post_ideas_storage.add_post_idea_to_file("💡 Уже в базе")
        self.txt_path.write_bytes(b"\xff\xfe")

        with self.assertRaises(UnicodeDecodeError):
            post_ideas_storage.migrate_post_ideas_from_txt(self.txt_path)

        self.assertEqual(
            post_ideas_storage.load_post_ideas(),
            ["💡 Уже в базе"],
        )
