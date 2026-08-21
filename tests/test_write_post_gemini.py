import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import httpx
from google.genai._gaos.lib.compat_errors import (
    APIConnectionError as GeminiAPIConnectionError,
)

from services import write_post as write_post_service
from services import write_post_gemini


class FakeAPIError(Exception):
    def __init__(self, message="API error", code=None):
        super().__init__(message)
        self.code = code


class FakeClientError(FakeAPIError):
    pass


class FakeServerError(FakeAPIError):
    pass


class FakeUnknownApiResponseError(ValueError):
    pass


class GeminiWritePostTests(unittest.TestCase):
    def run_generation(
        self,
        output_text="Готовый пост",
        create_error=None,
        client_error=None,
        client_ai_context=(
            "Название или имя клиента: Иван Иванов\n"
            "Instagram клиента: @ivan\n"
            "Информация о клиенте: Семейная кофейня"
        ),
        topic="Как выбрать кофе",
        style="Экспертный",
    ):
        captured = {}

        class FakeInteractions:
            def create(self, **kwargs):
                captured.update(kwargs)

                if create_error is not None:
                    raise create_error

                return SimpleNamespace(
                    output_text=output_text,
                )

        class FakeClient:
            def __init__(self):
                self.interactions = FakeInteractions()

        def create_client():
            if client_error is not None:
                raise client_error

            return FakeClient()

        google_module = ModuleType("google")
        genai_module = ModuleType("google.genai")
        errors_module = ModuleType("google.genai.errors")

        genai_module.Client = create_client
        genai_module.errors = errors_module
        errors_module.APIError = FakeAPIError
        errors_module.ClientError = FakeClientError
        errors_module.ServerError = FakeServerError
        errors_module.UnknownApiResponseError = (
            FakeUnknownApiResponseError
        )
        google_module.genai = genai_module

        modules = {
            "google": google_module,
            "google.genai": genai_module,
            "google.genai.errors": errors_module,
        }

        with patch.dict(sys.modules, modules):
            result = write_post_gemini.generate_gemini_post(
                client_ai_context,
                topic,
                style,
            )

        return result, captured

    def assert_generation_error(self, **kwargs):
        with self.assertRaises(
            write_post_service.WritePostGenerationError
        ) as context:
            self.run_generation(**kwargs)

        return str(context.exception)

    def test_gemini_uses_the_shared_write_post_contract(self):
        self.assertIs(
            write_post_gemini.WRITE_POST_INSTRUCTIONS,
            write_post_service.WRITE_POST_AI_CONTRACT,
        )

    def test_generation_uses_required_parameters_and_input(self):
        result, captured = self.run_generation()

        self.assertEqual(result, "Готовый пост")
        self.assertEqual(
            captured,
            {
                "model": "gemini-3.6-flash",
                "input": (
                    "Контекст клиента:\n"
                    "Название или имя клиента: Иван Иванов\n"
                    "Instagram клиента: @ivan\n"
                    "Информация о клиенте: Семейная кофейня\n\n"
                    "Тема поста:\n"
                    "Как выбрать кофе\n\n"
                    "Стиль поста:\n"
                    "Экспертный"
                ),
                "system_instruction": (
                    write_post_gemini.WRITE_POST_INSTRUCTIONS
                ),
                "generation_config": {
                    "thinking_level": "low",
                },
                "store": False,
                "response_format": {
                    "type": "text",
                },
            },
        )

    def test_generation_without_client_uses_explicit_fallback(self):
        _, captured = self.run_generation(
            client_ai_context="",
            topic="Тема без клиента",
            style="Дружелюбный",
        )

        self.assertIn(
            "Контекст клиента:\nНе указан.",
            captured["input"],
        )
        self.assertIn(
            "Тема поста:\nТема без клиента",
            captured["input"],
        )
        self.assertIn(
            "Стиль поста:\nДружелюбный",
            captured["input"],
        )

    def test_successful_text_is_stripped(self):
        result, _ = self.run_generation(
            output_text="  Готовый пост\n"
        )

        self.assertEqual(result, "Готовый пост")

    def test_empty_or_invalid_output_raises_generation_error(self):
        for output_text in (None, "", "   ", {"text": "Пост"}):
            with self.subTest(output_text=output_text):
                message = self.assert_generation_error(
                    output_text=output_text
                )

                self.assertIn(
                    "не сформировал текст поста",
                    message,
                )

    def test_expected_provider_errors_are_mapped(self):
        errors = (
            (
                FakeClientError("Unauthorized", code=401),
                "авторизоваться в Gemini",
            ),
            (
                FakeClientError("Rate limit", code=429),
                "ограничил число запросов",
            ),
            (
                FakeServerError("Server error", code=500),
                "ошибку сервиса",
            ),
            (
                FakeAPIError("API error"),
                "получить ответ Gemini",
            ),
            (
                FakeUnknownApiResponseError("Unknown response"),
                "получить ответ Gemini",
            ),
        )

        for error, expected_message in errors:
            with self.subTest(error=error):
                message = self.assert_generation_error(
                    create_error=error
                )

                self.assertIn(expected_message, message)

    def test_missing_api_key_is_mapped(self):
        message = self.assert_generation_error(
            client_error=ValueError(
                "Missing key inputs argument! "
                "Provide an api_key."
            )
        )

        self.assertIn("авторизоваться в Gemini", message)

    def test_network_error_is_mapped(self):
        request = httpx.Request(
            "POST",
            "https://example.invalid",
        )
        errors = (
            httpx.ConnectError(
                "Connection failed",
                request=request,
            ),
            GeminiAPIConnectionError(request=request),
        )

        for error in errors:
            with self.subTest(error=type(error).__name__):
                message = self.assert_generation_error(
                    create_error=error
                )

                self.assertIn("сейчас не отвечает", message)

    def test_unexpected_runtime_error_is_not_masked(self):
        runtime_error = RuntimeError("Programming error")

        with self.assertRaises(RuntimeError) as context:
            self.run_generation(create_error=runtime_error)

        self.assertIs(context.exception, runtime_error)


class WritePostGeminiServiceTests(unittest.TestCase):
    def setUp(self):
        self.client_context = {
            "name": " Иван ",
            "last_name": " Иванов ",
            "phone": "+372 5555 0000",
            "instagram": " @ivan ",
            "email": "ivan@example.com",
            "notes": " Семейная кофейня ",
        }

    def test_client_ai_context_contains_only_safe_fields(self):
        context = write_post_service.build_client_ai_context(
            self.client_context
        )

        self.assertEqual(
            context,
            "Название или имя клиента: Иван Иванов\n"
            "Instagram клиента: @ivan\n"
            "Информация о клиенте: Семейная кофейня",
        )
        self.assertNotIn("+372 5555 0000", context)
        self.assertNotIn("ivan@example.com", context)

    def test_client_ai_context_handles_missing_client(self):
        self.assertEqual(
            write_post_service.build_client_ai_context(None),
            "",
        )

    def test_success_creates_exact_post_and_saves_once(self):
        existing_posts = [
            {
                "id": 7,
                "client": "Старый клиент",
                "client_context": None,
                "topic": "Старая тема",
                "style": "Информационный",
                "text": "Старый текст",
            },
            {"id": "100", "text": "Старый ID"},
        ]
        original_posts = list(existing_posts)
        add_post = Mock()

        with (
            patch.object(
                write_post_gemini,
                "generate_gemini_post",
                return_value="AI-текст",
            ) as generate_post,
            patch.object(
                write_post_service.posts_storage,
                "load_posts",
                return_value=existing_posts,
            ),
            patch.object(
                write_post_service.posts_storage,
                "add_post",
                add_post,
            ),
        ):
            post = (
                write_post_service.create_and_save_gemini_post(
                    "Иван Иванов",
                    self.client_context,
                    "Как выбрать кофе",
                    "Экспертный",
                )
            )

        generate_post.assert_called_once_with(
            "Название или имя клиента: Иван Иванов\n"
            "Instagram клиента: @ivan\n"
            "Информация о клиенте: Семейная кофейня",
            "Как выбрать кофе",
            "Экспертный",
        )
        self.assertEqual(
            post,
            {
                "id": 8,
                "client": "Иван Иванов",
                "client_context": self.client_context,
                "topic": "Как выбрать кофе",
                "style": "Экспертный",
                "text": "AI-текст",
            },
        )
        self.assertEqual(existing_posts, original_posts)
        add_post.assert_called_once_with(post)

    def test_generation_error_does_not_load_or_save_posts(self):
        generation_error = (
            write_post_service.WritePostGenerationError(
                "Gemini недоступен"
            )
        )

        with (
            patch.object(
                write_post_gemini,
                "generate_gemini_post",
                side_effect=generation_error,
            ),
            patch.object(
                write_post_service.posts_storage,
                "load_posts",
            ) as load_posts,
            patch.object(
                write_post_service.posts_storage,
                "add_post",
            ) as add_post,
        ):
            with self.assertRaises(
                write_post_service.WritePostGenerationError
            ) as context:
                write_post_service.create_and_save_gemini_post(
                    "Иван Иванов",
                    self.client_context,
                    "Как выбрать кофе",
                    "Экспертный",
                )

        self.assertIs(context.exception, generation_error)
        load_posts.assert_not_called()
        add_post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
