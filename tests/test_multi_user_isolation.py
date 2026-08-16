import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services import clients as clients_service
from services import post_ideas as post_ideas_service
from storage import clients as clients_storage
from storage import content_plans as content_plans_storage
from storage import post_ideas as post_ideas_storage
from storage import posts as posts_storage


USER_A = 101
USER_B = 202


def make_client(name: str) -> dict:
    return {
        "name": name,
        "last_name": "Owner",
        "phone": "+372 5555 0000",
        "instagram": f"@{name.lower()}",
        "email": f"{name.lower()}@example.com",
        "notes": "Test client",
    }


def make_post(text: str) -> dict:
    return {
        "id": None,
        "client": "Client Owner",
        "client_context": None,
        "topic": "Test topic",
        "style": "Friendly",
        "text": text,
    }


class MultiUserIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        temporary_path = Path(self.temporary_directory.name)
        self.patches = [
            patch.object(clients_storage, "CLIENTS_DATABASE", str(temporary_path / "clients.db")),
            patch.object(post_ideas_storage, "POST_IDEAS_DATABASE", str(temporary_path / "post_ideas.db")),
            patch.object(posts_storage, "POSTS_DATABASE", str(temporary_path / "posts.db")),
            patch.object(content_plans_storage, "CONTENT_PLANS_DATABASE", str(temporary_path / "content_plans.db")),
        ]
        for database_patch in self.patches:
            database_patch.start()
            self.addCleanup(database_patch.stop)

    def test_clients_are_visible_and_searchable_only_to_their_owner(self):
        clients_storage.add_client(make_client("Alice"), USER_A)
        clients_storage.add_client(make_client("Bob"), USER_B)

        self.assertEqual(clients_storage.load_clients(USER_A), [make_client("Alice")])
        self.assertEqual(clients_storage.load_clients(USER_B), [make_client("Bob")])
        self.assertEqual(clients_service.search_clients("bob", USER_A), [])
        self.assertEqual(clients_service.search_clients("bob", USER_B), [make_client("Bob")])

    def test_same_post_idea_is_allowed_for_different_owners_and_random_source_is_isolated(self):
        self.assertEqual(
            post_ideas_service.create_post_idea("Coffee story", USER_A)[0],
            post_ideas_service.IDEA_OPERATION_READY,
        )
        self.assertEqual(
            post_ideas_service.create_post_idea("Coffee story", USER_B)[0],
            post_ideas_service.IDEA_OPERATION_READY,
        )
        post_ideas_storage.add_post_idea_to_file("Only B", USER_B)

        self.assertEqual(
            post_ideas_storage.load_post_ideas(USER_A),
            ["💡 Coffee story"],
        )
        self.assertEqual(
            post_ideas_storage.load_post_ideas(USER_B),
            ["💡 Coffee story", "Only B"],
        )

    def test_direct_post_id_update_and_delete_cannot_cross_owner_boundary(self):
        post_a_id = posts_storage.add_post(make_post("Post A"), USER_A)
        post_b_id = posts_storage.add_post(make_post("Post B"), USER_B)

        self.assertFalse(posts_storage.delete_post_by_id(post_b_id, USER_A))
        self.assertFalse(posts_storage.update_post_by_id(post_b_id, make_post("Changed"), USER_A))
        self.assertEqual(posts_storage.load_posts(USER_A)[0]["id"], post_a_id)
        self.assertEqual(posts_storage.load_posts(USER_B)[0]["text"], "Post B")

    def test_content_plans_are_saved_and_deleted_only_for_their_owner_after_reopen(self):
        content_plans_storage.add_content_plan("Plan A", USER_A)
        content_plans_storage.add_content_plan("Plan B", USER_B)

        self.assertEqual(content_plans_storage.read_content_plans(USER_A), ["Plan A"])
        self.assertEqual(content_plans_storage.read_content_plans(USER_B), ["Plan B"])
        self.assertFalse(content_plans_storage.delete_content_plan_by_position(2, USER_A))
        self.assertEqual(content_plans_storage.read_content_plans(USER_B), ["Plan B"])
        self.assertTrue(content_plans_storage.delete_content_plan_by_position(1, USER_A))
        self.assertEqual(content_plans_storage.read_content_plans(USER_A), [])

    def test_legacy_rows_remain_unassigned_and_hidden_from_regular_users(self):
        clients_storage.add_client(make_client("Legacy"))
        post_ideas_storage.add_post_idea_to_file("Legacy idea")
        posts_storage.add_post(make_post("Legacy post"))
        content_plans_storage.add_content_plan("Legacy plan")

        self.assertEqual(clients_storage.load_clients(USER_A), [])
        self.assertEqual(post_ideas_storage.load_post_ideas(USER_A), [])
        self.assertEqual(posts_storage.load_posts(USER_A), [])
        self.assertEqual(content_plans_storage.read_content_plans(USER_A), [])
        self.assertEqual(clients_storage.load_clients(), [make_client("Legacy")])

    def test_legacy_rows_become_visible_only_after_explicit_assignment(self):
        clients_storage.add_client(make_client("Legacy"))

        self.assertEqual(clients_storage.load_clients(USER_A), [])
        self.assertEqual(clients_storage.assign_legacy_clients(USER_A), 1)
        self.assertEqual(
            clients_storage.load_clients(USER_A),
            [make_client("Legacy")],
        )


class OwnerSchemaMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.temporary_path = Path(self.temporary_directory.name)

    def test_old_schema_gains_nullable_owner_without_losing_rows_or_exposing_them(self):
        cases = [
            (clients_storage, "CLIENTS_DATABASE", "clients.db", "CREATE TABLE clients (id INTEGER PRIMARY KEY, name TEXT, last_name TEXT, phone TEXT, instagram TEXT, email TEXT, notes TEXT)", "INSERT INTO clients VALUES (1, 'Legacy', 'Owner', '', '', '', '')", clients_storage.initialize_clients_storage, lambda: clients_storage.load_clients(USER_A)),
            (post_ideas_storage, "POST_IDEAS_DATABASE", "post_ideas.db", "CREATE TABLE post_ideas (id INTEGER PRIMARY KEY, text TEXT)", "INSERT INTO post_ideas VALUES (1, 'Legacy idea')", post_ideas_storage.initialize_post_ideas_storage, lambda: post_ideas_storage.load_post_ideas(USER_A)),
            (posts_storage, "POSTS_DATABASE", "posts.db", "CREATE TABLE posts (id INTEGER PRIMARY KEY, client TEXT, client_context TEXT, topic TEXT, style TEXT, text TEXT)", "INSERT INTO posts VALUES (1, 'Legacy', NULL, 'Topic', 'Style', 'Text')", posts_storage.initialize_posts_storage, lambda: posts_storage.load_posts(USER_A)),
            (content_plans_storage, "CONTENT_PLANS_DATABASE", "content_plans.db", "CREATE TABLE content_plans (id INTEGER PRIMARY KEY, text TEXT)", "INSERT INTO content_plans VALUES (1, 'Legacy plan')", content_plans_storage.initialize_content_plans_storage, lambda: content_plans_storage.read_content_plans(USER_A)),
        ]

        for module, database_name, filename, create_sql, insert_sql, initialize, load_for_user in cases:
            database_path = self.temporary_path / filename
            connection = sqlite3.connect(database_path)
            try:
                connection.execute(create_sql)
                connection.execute(insert_sql)
                connection.commit()
            finally:
                connection.close()

            with patch.object(module, database_name, str(database_path)):
                initialize()
                initialize()
                connection = sqlite3.connect(database_path)
                try:
                    columns = {
                        row[1]
                        for row in connection.execute(
                            "PRAGMA table_info(" + filename.removesuffix(".db") + ")"
                        )
                    }
                    owner = connection.execute(
                        "SELECT telegram_user_id FROM " + filename.removesuffix(".db") + " WHERE id = 1"
                    ).fetchone()[0]
                finally:
                    connection.close()
                self.assertIn("telegram_user_id", columns)
                self.assertIsNone(owner)
                self.assertEqual(load_for_user(), [])
