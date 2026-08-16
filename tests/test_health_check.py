import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

from scripts import check_health


class HealthCheckTests(unittest.IsolatedAsyncioTestCase):
    async def test_success_checks_redis_and_existing_temporary_database_without_ai_keys(self):
        with TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "clients.db"
            import sqlite3

            connection = sqlite3.connect(database_path)
            try:
                connection.execute("CREATE TABLE clients (id INTEGER PRIMARY KEY)")
                connection.commit()
            finally:
                connection.close()

            databases = {"clients": (lambda: database_path, "clients")}
            with (
                patch.object(check_health, "DATABASES", databases),
                patch.object(check_health, "check_redis", AsyncMock()) as redis,
            ):
                healthy, messages = await check_health.run_health_check(
                    {
                        "TELEGRAM_BOT_TOKEN": "test-token",
                        "FSM_REDIS_URL": "redis://test/0",
                    }
                )

        self.assertTrue(healthy)
        self.assertEqual(messages, ["ready"])
        redis.assert_awaited_once_with("redis://test/0")

    async def test_redis_unavailable_fails_without_exposing_url(self):
        with patch.object(
            check_health,
            "check_redis",
            AsyncMock(side_effect=ConnectionError("redis://secret@host")),
        ):
            healthy, messages = await check_health.run_health_check(
                {
                    "TELEGRAM_BOT_TOKEN": "test-token",
                    "FSM_REDIS_URL": "redis://secret@host",
                }
            )

        self.assertFalse(healthy)
        self.assertEqual(messages, ["Redis FSM backend is unavailable"])
        self.assertNotIn("secret", messages[0])

    async def test_missing_required_configuration_returns_safe_failure(self):
        healthy, messages = await check_health.run_health_check({})

        self.assertFalse(healthy)
        self.assertEqual(messages, ["required configuration is missing"])

    async def test_missing_optional_database_is_not_created(self):
        with TemporaryDirectory() as temporary_directory:
            missing_database = Path(temporary_directory) / "missing.db"
            databases = {"clients": (lambda: missing_database, "clients")}
            with (
                patch.object(check_health, "DATABASES", databases),
                patch.object(check_health, "check_redis", AsyncMock()),
            ):
                healthy, _ = await check_health.run_health_check(
                    {
                        "TELEGRAM_BOT_TOKEN": "test-token",
                        "FSM_REDIS_URL": "redis://test/0",
                    }
                )

        self.assertTrue(healthy)
        self.assertFalse(missing_database.exists())


class DeploymentTemplateTests(unittest.TestCase):
    def test_templates_contain_placeholders_not_secrets_and_private_umask(self):
        project_root = Path(__file__).parents[1]
        service = (project_root / "deploy" / "smm-bot.service.example").read_text()
        backup_service = (
            project_root / "deploy" / "smm-bot-backup.service.example"
        ).read_text()

        self.assertIn("User=<BOT_USER>", service)
        self.assertIn("EnvironmentFile=<ENVIRONMENT_FILE>", service)
        self.assertIn("Restart=on-failure", service)
        self.assertIn("UMask=0077", service)
        self.assertIn("UMask=0077", backup_service)
        self.assertNotIn("TELEGRAM_BOT_TOKEN=", service)
        self.assertNotIn("redis://", service)
