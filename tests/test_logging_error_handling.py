import logging
import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import main as bot_main


class FakeMessage:
    def __init__(self):
        self.answer = AsyncMock()


def error_with_secret(error_type=RuntimeError):
    secret = "super-secret-value"
    try:
        raise error_type(secret)
    except error_type as error:
        return error


class LoggingConfigurationTests(unittest.TestCase):
    def test_invalid_log_level_falls_back_to_info(self):
        self.assertEqual(bot_main.get_log_level("unexpected"), logging.INFO)
        self.assertEqual(bot_main.get_log_level(None), logging.INFO)
        self.assertEqual(bot_main.get_log_level("warning"), logging.WARNING)

    def test_logging_uses_safe_standard_format(self):
        with patch.object(logging, "basicConfig") as basic_config:
            bot_main.configure_logging("DEBUG")

        basic_config.assert_called_once_with(
            level=logging.DEBUG,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )


class GlobalTelegramErrorHandlingTests(unittest.IsolatedAsyncioTestCase):
    async def test_unexpected_error_is_logged_without_secret_and_user_gets_safe_message(self):
        message = FakeMessage()
        error = error_with_secret()
        event = SimpleNamespace(
            exception=error,
            update=SimpleNamespace(message=message),
        )

        with self.assertLogs("main", level="ERROR") as captured:
            await bot_main.handle_unexpected_telegram_error(event)

        logged = "\n".join(captured.output)
        self.assertIn("RuntimeError", logged)
        self.assertNotIn("super-secret-value", logged)
        message.answer.assert_awaited_once_with(
            bot_main.USER_SAFE_ERROR_MESSAGE
        )
        self.assertNotIn("RuntimeError", bot_main.USER_SAFE_ERROR_MESSAGE)

    async def test_database_error_does_not_report_success_or_clear_fsm(self):
        message = FakeMessage()
        event = SimpleNamespace(
            exception=error_with_secret(sqlite3.OperationalError),
            update=SimpleNamespace(message=message),
        )

        await bot_main.handle_unexpected_telegram_error(event)

        reply = message.answer.await_args.args[0]
        self.assertEqual(reply, bot_main.USER_SAFE_ERROR_MESSAGE)
        self.assertNotIn("успеш", reply.lower())
        self.assertNotIn("sqlite", reply.lower())

    async def test_callback_query_error_uses_its_message_for_safe_reply(self):
        message = FakeMessage()
        event = SimpleNamespace(
            exception=error_with_secret(),
            update=SimpleNamespace(
                message=None,
                callback_query=SimpleNamespace(message=message),
            ),
        )

        await bot_main.handle_unexpected_telegram_error(event)

        message.answer.assert_awaited_once_with(
            bot_main.USER_SAFE_ERROR_MESSAGE
        )

    async def test_error_message_delivery_failure_does_not_raise_another_error(self):
        message = FakeMessage()
        message.answer.side_effect = RuntimeError("delivery failed")
        event = SimpleNamespace(
            exception=error_with_secret(),
            update=SimpleNamespace(message=message),
        )

        with self.assertLogs("main", level="ERROR") as captured:
            await bot_main.handle_unexpected_telegram_error(event)

        self.assertIn("Could not deliver safe error message", captured.output[-1])
