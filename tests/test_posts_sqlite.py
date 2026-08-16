import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services import write_post as write_post_service
from storage import posts as posts_storage


def make_post(
    post_id=1,
    client="Иван Иванов",
    client_context=None,
    topic="Тема",
    style="Дружелюбный",
    text="Текст поста",
):
    return {
        "id": post_id,
        "client": client,
        "client_context": client_context,
        "topic": topic,
        "style": style,
        "text": text,
    }


class PostsSQLiteTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        temporary_path = Path(self.temporary_directory.name)
        self.database_path = temporary_path / "posts.db"
        self.txt_path = temporary_path / "posts.txt"
        self.database_patch = patch.object(
            posts_storage,
            "POSTS_DATABASE",
            str(self.database_path),
        )
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)

    def test_new_database_is_empty_and_reopens_with_saved_post(self):
        self.assertEqual(posts_storage.load_posts(), [])

        posts_storage.add_post(make_post(client_context={"name": "Иван"}))

        self.assertEqual(
            posts_storage.load_posts(),
            [make_post(client_context={"name": "Иван"})],
        )

    def test_records_keep_stable_ids_after_update_and_delete(self):
        posts_storage.add_post(make_post(post_id=1, text="Первый"))
        posts_storage.add_post(make_post(post_id=2, text="Второй"))

        self.assertTrue(
            posts_storage.update_post_by_id(
                2,
                make_post(post_id=2, text="Обновлённый второй"),
            )
        )
        self.assertTrue(posts_storage.delete_post_by_id(1))
        posts_storage.add_post(make_post(post_id=3, text="Третий"))

        posts = posts_storage.load_posts()
        self.assertEqual([post["id"] for post in posts], [2, 3])
        self.assertEqual(posts[0]["text"], "Обновлённый второй")

    def test_template_and_ai_save_paths_preserve_client_contract(self):
        client_context = {
            "name": "Иван",
            "last_name": "Иванов",
            "phone": "+372 5555 0000",
            "instagram": "@ivan",
            "email": "ivan@example.com",
            "notes": "Постоянный клиент",
        }
        template_post = write_post_service.create_and_save_post(
            "Иван Иванов",
            client_context,
            "Тема по шаблону",
            "Дружелюбный",
        )

        with patch.object(
            write_post_service,
            "generate_ai_post",
            return_value="AI-текст",
        ):
            ai_post = write_post_service.create_and_save_ai_post(
                "gemini",
                "",
                None,
                "AI-тема",
                "Информационный",
            )

        self.assertEqual(template_post["id"], 1)
        self.assertEqual(template_post["client_context"], client_context)
        self.assertEqual(ai_post["id"], 2)
        self.assertEqual(ai_post["client"], "")
        self.assertIsNone(ai_post["client_context"])
        self.assertEqual(ai_post["text"], "AI-текст")
        self.assertEqual(
            write_post_service.find_posts(
                posts_storage.load_posts(),
                "ai-тема",
            ),
            [ai_post],
        )

    def test_delete_service_removes_only_selected_post(self):
        posts_storage.add_post(make_post(post_id=1, text="Первый"))
        posts_storage.add_post(make_post(post_id=2, text="Второй"))

        deleted, post = write_post_service.delete_post(1)

        self.assertTrue(deleted)
        self.assertEqual(post["text"], "Первый")
        self.assertEqual(posts_storage.load_posts(), [make_post(post_id=2, text="Второй")])

    def test_migration_is_idempotent_and_leaves_txt_unchanged(self):
        source_posts = [
            make_post(
                post_id=2,
                client_context={"name": "Иван", "notes": "Клиент"},
                topic="Тема 1",
            ),
            make_post(
                post_id=5,
                client="",
                client_context=None,
                topic="Тема 2",
            ),
        ]
        source_text = __import__("json").dumps(
            source_posts,
            ensure_ascii=False,
            indent=4,
        )
        self.txt_path.write_text(source_text, encoding="utf-8")

        first = posts_storage.migrate_posts_from_txt(self.txt_path)
        second = posts_storage.migrate_posts_from_txt(self.txt_path)

        self.assertEqual(first.migrated_count, 2)
        self.assertFalse(first.already_migrated)
        self.assertEqual(second.migrated_count, 0)
        self.assertTrue(second.already_migrated)
        self.assertEqual(self.txt_path.read_text(encoding="utf-8"), source_text)
        self.assertEqual(posts_storage.load_posts(), source_posts)

    def test_migration_of_empty_or_invalid_txt_does_not_partially_change_database(self):
        self.txt_path.write_text("[]", encoding="utf-8")
        result = posts_storage.migrate_posts_from_txt(self.txt_path)
        self.assertTrue(result.source_found)
        self.assertEqual(result.migrated_count, 0)
        self.assertEqual(posts_storage.load_posts(), [])

        self.database_path.unlink()
        posts_storage.add_post(make_post())
        self.txt_path.write_text("{invalid json", encoding="utf-8")

        with self.assertRaises(ValueError):
            posts_storage.migrate_posts_from_txt(self.txt_path)

        self.assertEqual(posts_storage.load_posts(), [make_post()])
