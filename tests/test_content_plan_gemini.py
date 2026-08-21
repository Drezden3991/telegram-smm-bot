import json
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import httpx
from google.genai._gaos.lib.compat_errors import (
    APIConnectionError as GeminiAPIConnectionError,
)

from models.content_plan import SevenDayContentPlan
from services import content_plan as content_plan_service
from services import content_plan_gemini


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


def make_plan_json(day_numbers=range(1, 8)):
    return json.dumps(
        {
            "days": [
                {
                    "day": day,
                    "goal": f"Цель {day}",
                    "topic": f"Тема {day}",
                    "format": "Текстовый пост",
                    "key_message": f"Ключевой тезис {day}",
                    "cta": f"Действие {day}",
                }
                for day in day_numbers
            ]
        },
        ensure_ascii=False,
    )


class GeminiContentPlanTests(unittest.TestCase):
    def run_generation(
        self,
        output_text=None,
        create_error=None,
        client_error=None,
        brief="Тестовый бриф",
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
            result = (
                content_plan_gemini.generate_gemini_content_plan(
                    brief
                )
            )

        return result, captured

    def assert_generation_error(self, **kwargs):
        with self.assertRaises(
            content_plan_service.ContentPlanGenerationError
        ) as context:
            self.run_generation(**kwargs)

        return str(context.exception)

    def test_success_uses_required_interactions_parameters(self):
        result, captured = self.run_generation(
            output_text=make_plan_json()
        )

        self.assertIsInstance(result, SevenDayContentPlan)
        self.assertEqual(
            [item.day for item in result.days],
            list(range(1, 8)),
        )
        self.assertEqual(
            captured,
            {
                "model": "gemini-3.6-flash",
                "input": (
                    "Краткий бриф пользователя:\n"
                    "Тестовый бриф"
                ),
                "system_instruction": (
                    content_plan_gemini.GEMINI_CONTENT_PLAN_INSTRUCTIONS
                ),
                "generation_config": {
                    "thinking_level": "low",
                },
                "store": False,
                "response_format": {
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": (
                        SevenDayContentPlan.model_json_schema()
                    ),
                },
            },
        )

    def test_gemini_uses_the_shared_content_plan_contract(self):
        self.assertIs(
            content_plan_gemini.GEMINI_CONTENT_PLAN_INSTRUCTIONS,
            content_plan_service.CONTENT_PLAN_AI_CONTRACT,
        )

    def test_instruction_and_schema_descriptions_state_limits(self):
        _, captured = self.run_generation(
            output_text=make_plan_json()
        )

        instruction = captured["system_instruction"]

        for field_name, max_length in (
            ("goal", 50),
            ("topic", 90),
            ("format", 30),
            ("key_message", 120),
            ("cta", 70),
        ):
            with self.subTest(field_name=field_name):
                self.assertIn(
                    f"{field_name} — не более {max_length} символов",
                    instruction,
                )

        properties = captured["response_format"]["schema"][
            "$defs"
        ]["ContentPlanDay"]["properties"]

        self.assertEqual(
            properties["goal"]["description"],
            "Цель дня: не более 50 символов.",
        )
        self.assertEqual(
            properties["topic"]["description"],
            "Тема публикации: не более 90 символов.",
        )
        self.assertEqual(
            properties["format"]["description"],
            "Формат публикации: не более 30 символов.",
        )
        self.assertEqual(
            properties["key_message"]["description"],
            "Ключевой тезис: не более 120 символов.",
        )
        self.assertEqual(
            properties["cta"]["description"],
            "Призыв к действию: не более 70 символов.",
        )

    def test_instruction_prohibits_unsupported_client_facts(self):
        _, captured = self.run_generation(
            output_text=make_plan_json()
        )

        instruction = captured["system_instruction"].lower()

        for fragment in (
            "подтверждённые факты о клиенте",
            "только сведения, явно указанные во входном контексте",
            "не даёт права утверждать его существование",
            "общие знания",
            "неподтверждённое утверждение о клиенте",
            "wi-fi",
            "розеток",
            "скидок",
            "промокодов",
            "отзывов",
            "товаров или услуг",
            "формулируй тему нейтрально",
            "для раскрытия и уточнения",
            "разделяй тему будущего поста и факт о клиенте",
            "не существующим свойством бизнеса",
            "не используй от имени клиента формулировки",
            "key_message должен содержать только",
            "нейтральную общую мысль",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, instruction)

    def test_generation_receives_labeled_confirmed_facts_block(self):
        brief = content_plan_service.build_ai_brief(
            {
                "name": "Coffee Lab Tallinn",
                "instagram": "@coffeelab_test",
                "notes": "Небольшая современная кофейня",
            },
            ["Объяснить особенности specialty coffee"],
            "Привлечь новую аудиторию",
        )

        _, captured = self.run_generation(
            output_text=make_plan_json(),
            brief=brief,
        )

        self.assertIn(
            "ПОДТВЕРЖДЁННЫЕ ФАКТЫ О КЛИЕНТЕ:",
            captured["input"],
        )
        self.assertIn(
            "ВЫБРАННЫЕ ИДЕИ:",
            captured["input"],
        )
        self.assertIn(
            "ПОЛЬЗОВАТЕЛЬСКАЯ ЗАДАЧА:",
            captured["input"],
        )

    def test_six_days_raise_generation_error(self):
        message = self.assert_generation_error(
            output_text=make_plan_json(range(1, 7))
        )

        self.assertIn("неполный контент-план", message)

    def test_eight_days_raise_generation_error(self):
        message = self.assert_generation_error(
            output_text=make_plan_json(range(1, 9))
        )

        self.assertIn("неполный контент-план", message)

    def test_wrong_day_order_raises_generation_error(self):
        message = self.assert_generation_error(
            output_text=make_plan_json(
                [1, 2, 4, 3, 5, 6, 7]
            )
        )

        self.assertIn("дни в неверном порядке", message)

    def test_empty_output_text_raises_generation_error(self):
        for output_text in (None, "", "   "):
            with self.subTest(output_text=output_text):
                message = self.assert_generation_error(
                    output_text=output_text
                )

                self.assertIn(
                    "не сформировал контент-план",
                    message,
                )

    def test_invalid_json_raises_generation_error(self):
        message = self.assert_generation_error(
            output_text="{повреждённый json"
        )

        self.assertIn("неполный контент-план", message)

    def test_authentication_errors_raise_generation_error(self):
        errors = (
            FakeClientError("Unauthorized", code=401),
            FakeClientError("Forbidden", code=403),
            FakeClientError("API_KEY_INVALID", code=400),
        )

        for error in errors:
            with self.subTest(error=error):
                message = self.assert_generation_error(
                    create_error=error
                )

                self.assertIn(
                    "авторизоваться в Gemini",
                    message,
                )

    def test_missing_api_key_raises_generation_error(self):
        message = self.assert_generation_error(
            client_error=ValueError(
                "Missing key inputs argument! "
                "Provide an api_key."
            )
        )

        self.assertIn("авторизоваться в Gemini", message)

    def test_rate_limit_error_raises_generation_error(self):
        message = self.assert_generation_error(
            create_error=FakeClientError(
                "Too many requests",
                code=429,
            )
        )

        self.assertIn("ограничил число запросов", message)

    def test_other_api_errors_raise_generation_error(self):
        errors = (
            FakeClientError("Bad request", code=400),
            FakeServerError("Server error", code=500),
            FakeAPIError("Generic API error"),
            FakeUnknownApiResponseError("Unknown response"),
        )

        for error in errors:
            with self.subTest(error=error):
                message = self.assert_generation_error(
                    create_error=error
                )

                self.assertIn("Gemini", message)

    def test_network_error_raises_generation_error(self):
        request = httpx.Request(
            "POST",
            "https://generativelanguage.googleapis.com",
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

                self.assertIn("Gemini сейчас не отвечает", message)

    def test_unexpected_runtime_error_is_not_masked(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "Programming error",
        ):
            self.run_generation(
                create_error=RuntimeError(
                    "Programming error"
                )
            )


if __name__ == "__main__":
    unittest.main()
