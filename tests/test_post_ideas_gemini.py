import json
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import httpx
from google.genai._gaos.lib.compat_errors import (
    APIConnectionError as GeminiAPIConnectionError,
)

from models.post_idea import GeneratedPostIdeas
from services import post_ideas as post_ideas_service
from services import post_ideas_gemini


DEFAULT_OUTPUT = object()


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


def make_ideas_json(ideas=None):
    if ideas is None:
        ideas = [
            "Как выбрать кофе для дома",
            "Пять ошибок при заказе кофе",
            "Как хранить кофейные зёрна",
        ]

    return json.dumps(
        {"ideas": ideas},
        ensure_ascii=False,
    )


class GeminiPostIdeasTests(unittest.TestCase):
    def run_generation(
        self,
        output_text=DEFAULT_OUTPUT,
        create_error=None,
        client_error=None,
        client_ai_context=(
            "Название или имя клиента: Иван Иванов\n"
            "Instagram клиента: @ivan\n"
            "Информация о клиенте: Семейная кофейня"
        ),
        brief="Идеи для кофейни",
        existing_ideas=None,
    ):
        if output_text is DEFAULT_OUTPUT:
            output_text = make_ideas_json()

        if existing_ideas is None:
            existing_ideas = [
                "💡 История появления эспрессо",
                "💡 Разница между арабикой и робустой",
            ]

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
            result = (
                post_ideas_gemini.generate_gemini_post_ideas(
                    client_ai_context,
                    brief,
                    existing_ideas,
                )
            )

        return result, captured

    def assert_generation_error(self, **kwargs):
        with self.assertRaises(
            post_ideas_service.PostIdeasGenerationError
        ) as context:
            self.run_generation(**kwargs)

        return str(context.exception)

    def test_gemini_uses_the_shared_post_ideas_contract(self):
        self.assertIs(
            post_ideas_gemini.POST_IDEAS_INSTRUCTIONS,
            post_ideas_service.POST_IDEAS_AI_CONTRACT,
        )

    def test_generation_uses_required_parameters_and_context(self):
        result, captured = self.run_generation()

        self.assertIsInstance(result, GeneratedPostIdeas)
        self.assertEqual(
            result.ideas,
            [
                "Как выбрать кофе для дома",
                "Пять ошибок при заказе кофе",
                "Как хранить кофейные зёрна",
            ],
        )
        self.assertEqual(captured["model"], "gemini-3.6-flash")
        self.assertIs(
            captured["system_instruction"],
            post_ideas_gemini.POST_IDEAS_INSTRUCTIONS,
        )
        self.assertEqual(
            captured["generation_config"],
            {"thinking_level": "low"},
        )
        self.assertFalse(captured["store"])
        self.assertEqual(
            captured["response_format"],
            {
                "type": "text",
                "mime_type": "application/json",
                "schema": GeneratedPostIdeas.model_json_schema(),
            },
        )
        self.assertIn(
            "Бриф или тема пользователя:\nИдеи для кофейни",
            captured["input"],
        )
        self.assertIn(
            "Название или имя клиента: Иван Иванов",
            captured["input"],
        )
        self.assertIn(
            "1. 💡 История появления эспрессо\n"
            "2. 💡 Разница между арабикой и робустой",
            captured["input"],
        )

    def test_generated_ideas_are_trimmed(self):
        result, _ = self.run_generation(
            output_text=make_ideas_json(
                ["  Первая идея  ", "\nВторая идея", "Третья идея\t"]
            )
        )

        self.assertEqual(
            result.ideas,
            ["Первая идея", "Вторая идея", "Третья идея"],
        )

    def test_empty_output_raises_generation_error(self):
        for output_text in (None, "", "   "):
            with self.subTest(output_text=output_text):
                message = self.assert_generation_error(
                    output_text=output_text
                )

                self.assertIn("не сформировал идеи", message)

    def test_wrong_number_of_ideas_raises_generation_error(self):
        for ideas in (
            ["Первая", "Вторая"],
            ["Первая", "Вторая", "Третья", "Четвёртая"],
        ):
            with self.subTest(ideas=ideas):
                message = self.assert_generation_error(
                    output_text=make_ideas_json(ideas)
                )

                self.assertIn(
                    "некорректный список идей",
                    message,
                )

    def test_blank_idea_raises_generation_error(self):
        message = self.assert_generation_error(
            output_text=make_ideas_json(
                ["Первая", "   ", "Третья"]
            )
        )

        self.assertIn("некорректный список идей", message)

    def test_invalid_json_raises_generation_error(self):
        message = self.assert_generation_error(
            output_text="{повреждённый json"
        )

        self.assertIn("некорректный список идей", message)

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

    def test_missing_api_key_and_network_errors_are_mapped(self):
        message = self.assert_generation_error(
            client_error=ValueError(
                "Missing key inputs argument! "
                "Provide an api_key."
            )
        )
        self.assertIn("авторизоваться в Gemini", message)

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


class PostIdeasGeminiServiceTests(unittest.TestCase):
    def setUp(self):
        self.client = {
            "name": " Иван ",
            "last_name": " Иванов ",
            "phone": "+372 5555 0000",
            "instagram": " @ivan ",
            "email": "ivan@example.com",
            "notes": " Семейная кофейня ",
        }

    def test_generation_uses_safe_context_and_does_not_save(self):
        existing_ideas = ["💡 Существующая идея"]
        generated = GeneratedPostIdeas(
            ideas=["Первая", "Вторая", "Третья"]
        )

        with (
            patch.object(
                post_ideas_service.post_ideas_storage,
                "load_post_ideas",
                return_value=existing_ideas,
            ) as load_post_ideas,
            patch.object(
                post_ideas_service.post_ideas_storage,
                "add_post_ideas",
            ) as save_post_ideas,
            patch.object(
                post_ideas_gemini,
                "generate_gemini_post_ideas",
                return_value=generated,
            ) as generate_ideas,
        ):
            result = (
                post_ideas_service.generate_post_idea_candidates(
                    self.client,
                    "Идеи для кофейни",
                )
            )

        load_post_ideas.assert_called_once_with()
        save_post_ideas.assert_not_called()
        generate_ideas.assert_called_once_with(
            "Название или имя клиента: Иван Иванов\n"
            "Instagram клиента: @ivan\n"
            "Информация о клиенте: Семейная кофейня",
            "Идеи для кофейни",
            existing_ideas,
        )
        provider_context = generate_ideas.call_args.args[0]
        self.assertNotIn("+372 5555 0000", provider_context)
        self.assertNotIn("ivan@example.com", provider_context)
        self.assertEqual(result, ["Первая", "Вторая", "Третья"])

    def test_batch_save_adds_only_new_ideas_once(self):
        current_ideas = [
            "💡 Существующая идея",
            "💡 Другая идея",
        ]

        with (
            patch.object(
                post_ideas_service.post_ideas_storage,
                "load_post_ideas",
                return_value=current_ideas,
            ) as load_post_ideas,
            patch.object(
                post_ideas_service.post_ideas_storage,
                "add_post_ideas",
            ) as save_post_ideas,
        ):
            added, duplicates = (
                post_ideas_service.save_selected_post_ideas(
                    [
                        "  Новая идея  ",
                        "существующая ИДЕЯ",
                        "💡 Ещё одна идея",
                        "НОВАЯ ИДЕЯ",
                    ]
                )
            )

        load_post_ideas.assert_called_once_with()
        save_post_ideas.assert_called_once_with(
            [
                "💡 Новая идея",
                "💡 Ещё одна идея",
            ]
        )
        self.assertEqual(
            added,
            ["💡 Новая идея", "💡 Ещё одна идея"],
        )
        self.assertEqual(
            duplicates,
            ["💡 существующая ИДЕЯ", "💡 НОВАЯ ИДЕЯ"],
        )

    def test_batch_save_skips_write_when_all_are_duplicates(self):
        current_ideas = [
            "💡 Первая идея",
            "💡 Вторая идея",
        ]

        with (
            patch.object(
                post_ideas_service.post_ideas_storage,
                "load_post_ideas",
                return_value=current_ideas,
            ) as load_post_ideas,
            patch.object(
                post_ideas_service.post_ideas_storage,
                "add_post_ideas",
            ) as save_post_ideas,
        ):
            added, duplicates = (
                post_ideas_service.save_selected_post_ideas(
                    ["ПЕРВАЯ ИДЕЯ", "💡 вторая идея"]
                )
            )

        load_post_ideas.assert_called_once_with()
        save_post_ideas.assert_not_called()
        self.assertEqual(added, [])
        self.assertEqual(
            duplicates,
            ["💡 ПЕРВАЯ ИДЕЯ", "💡 вторая идея"],
        )


if __name__ == "__main__":
    unittest.main()
