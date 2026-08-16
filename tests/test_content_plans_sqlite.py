import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from models.content_plan import ContentPlanDay, SevenDayContentPlan
from services import content_plan as content_plan_service
from storage import content_plans as content_plans_storage


def make_seven_day_plan():
    return SevenDayContentPlan(
        days=[
            ContentPlanDay(
                day=day,
                goal=f"Цель {day}",
                topic=f"Тема {day}",
                format="Пост",
                key_message=f"Ключевой тезис {day}",
                cta=f"Действие {day}",
            )
            for day in range(1, 8)
        ]
    )


class ContentPlansSQLiteTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        temporary_path = Path(self.temporary_directory.name)
        self.database_path = temporary_path / "content_plans.db"
        self.txt_path = temporary_path / "content_plans.txt"
        self.database_patch = patch.object(
            content_plans_storage,
            "CONTENT_PLANS_DATABASE",
            str(self.database_path),
        )
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)

    def test_new_database_is_empty_and_reopens_with_saved_plan(self):
        self.assertEqual(content_plans_storage.read_content_plans(), [])

        content_plans_storage.add_content_plan("Первый план")

        self.assertEqual(
            content_plans_storage.read_content_plans(),
            ["Первый план"],
        )

    def test_ids_stay_stable_after_update_delete_and_new_plan(self):
        first_id = content_plans_storage.add_content_plan("Первый")
        second_id = content_plans_storage.add_content_plan("Второй")

        self.assertTrue(
            content_plans_storage.update_content_plan_by_position(
                2,
                "Обновлённый второй",
            )
        )
        self.assertTrue(
            content_plans_storage.delete_content_plan_by_position(1)
        )
        third_id = content_plans_storage.add_content_plan("Третий")

        self.assertEqual((first_id, second_id, third_id), (1, 2, 3))
        self.assertEqual(
            content_plans_storage.load_content_plan_records(),
            [
                {"id": 2, "text": "Обновлённый второй"},
                {"id": 3, "text": "Третий"},
            ],
        )

    def test_validated_seven_day_plan_and_client_snapshot_are_saved_as_exact_text(self):
        plan_text = content_plan_service.format_content_plan_text(
            "Иван Иванов",
            ["Идея для публикации"],
            "Новый бриф",
            make_seven_day_plan(),
        )

        content_plans_storage.add_content_plan(plan_text)

        self.assertEqual(
            content_plans_storage.read_content_plans(),
            [plan_text],
        )
        self.assertIn("Клиент: Иван Иванов", plan_text)
        self.assertEqual(
            content_plan_service.find_content_plans(
                content_plans_storage.read_content_plans(),
                "иван",
            ),
            [plan_text],
        )

    def test_service_operations_change_only_current_selected_plan(self):
        content_plans_storage.add_content_plan("Первый")
        content_plans_storage.add_content_plan("Второй")
        content_plans_storage.add_content_plan("Третий")

        deleted, deleted_plan, remaining = (
            content_plan_service.delete_content_plan(2, "Второй")
        )

        self.assertTrue(deleted)
        self.assertEqual(deleted_plan, "Второй")
        self.assertEqual(remaining, ["Первый", "Третий"])
        self.assertEqual(
            content_plans_storage.read_content_plans(),
            ["Первый", "Третий"],
        )

        replaced, updated = content_plan_service.replace_content_plan(
            2,
            "Третий",
            "Новая версия",
        )

        self.assertTrue(replaced)
        self.assertEqual(updated, ["Первый", "Новая версия"])
        self.assertEqual(
            content_plans_storage.read_content_plans(),
            ["Первый", "Новая версия"],
        )

    def test_stale_selection_does_not_change_database(self):
        content_plans_storage.add_content_plan("Текущая версия")

        deleted, _, plans = content_plan_service.delete_content_plan(
            1,
            "Устаревшая версия",
        )
        replaced, replacement_plans = (
            content_plan_service.replace_content_plan(
                1,
                "Устаревшая версия",
                "Новая версия",
            )
        )

        self.assertFalse(deleted)
        self.assertFalse(replaced)
        self.assertEqual(plans, ["Текущая версия"])
        self.assertEqual(replacement_plans, ["Текущая версия"])
        self.assertEqual(
            content_plans_storage.read_content_plans(),
            ["Текущая версия"],
        )

    def test_migration_is_idempotent_and_keeps_txt_unchanged(self):
        separator = content_plans_storage.SEPARATOR
        source_text = (
            f"Первый план\n{separator}\n"
            f"Второй план\n{separator}\n"
        )
        self.txt_path.write_text(source_text, encoding="utf-8")

        first = content_plans_storage.migrate_content_plans_from_txt(
            self.txt_path
        )
        second = content_plans_storage.migrate_content_plans_from_txt(
            self.txt_path
        )

        self.assertEqual(first.migrated_count, 2)
        self.assertFalse(first.already_migrated)
        self.assertEqual(second.migrated_count, 0)
        self.assertTrue(second.already_migrated)
        self.assertEqual(
            self.txt_path.read_text(encoding="utf-8"),
            source_text,
        )
        self.assertEqual(
            content_plans_storage.load_content_plan_records(),
            [
                {"id": 1, "text": "Первый план"},
                {"id": 2, "text": "Второй план"},
            ],
        )

    def test_migration_of_empty_or_missing_txt_creates_no_plans(self):
        self.txt_path.write_text("  \n\t", encoding="utf-8")

        empty_result = content_plans_storage.migrate_content_plans_from_txt(
            self.txt_path
        )

        self.assertTrue(empty_result.source_found)
        self.assertEqual(empty_result.migrated_count, 0)
        self.assertEqual(content_plans_storage.read_content_plans(), [])

    def test_unreadable_migration_source_does_not_create_partial_database(self):
        invalid_source = Path(self.temporary_directory.name) / "not-a-file"
        invalid_source.mkdir()

        with self.assertRaises(OSError):
            content_plans_storage.migrate_content_plans_from_txt(
                invalid_source
            )

        self.assertFalse(self.database_path.exists())
