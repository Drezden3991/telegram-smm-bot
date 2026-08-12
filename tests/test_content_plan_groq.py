import json
import os
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from models.content_plan import SevenDayContentPlan
from services import content_plan as content_plan_service
from services import content_plan_gemini
from services import content_plan_groq
from services import content_plan_openai as content_plan_openai_service


class FakeGroqError(Exception):
    pass


class FakeAuthenticationError(FakeGroqError):
    pass


class FakeRateLimitError(FakeGroqError):
    pass


class FakeAPITimeoutError(FakeGroqError):
    pass


class FakeAPIConnectionError(FakeGroqError):
    pass


class FakeAPIStatusError(FakeGroqError):
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


class GroqContentPlanTests(unittest.TestCase):
    def run_generation(
        self,
        output_text=None,
        create_error=None,
        brief="Тестовый бриф",
    ):
        captured = {}

        class FakeCompletions:
            def create(self, **kwargs):
                captured.update(kwargs)

                if create_error is not None:
                    raise create_error

                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content=output_text
                            )
                        )
                    ]
                )

        class FakeGroqClient:
            def __init__(self, **kwargs):
                captured["client"] = kwargs
                self.chat = SimpleNamespace(
                    completions=FakeCompletions()
                )

        groq_module = ModuleType("groq")
        groq_module.Groq = FakeGroqClient
        groq_module.GroqError = FakeGroqError
        groq_module.AuthenticationError = FakeAuthenticationError
        groq_module.RateLimitError = FakeRateLimitError
        groq_module.APITimeoutError = FakeAPITimeoutError
        groq_module.APIConnectionError = FakeAPIConnectionError
        groq_module.APIStatusError = FakeAPIStatusError

        with (
            patch.dict(sys.modules, {"groq": groq_module}),
            patch.dict(
                os.environ,
                {"GROQ_API_KEY": "test-groq-key"},
                clear=False,
            ),
        ):
            result = content_plan_groq.generate_groq_content_plan(
                brief
            )

        return result, captured

    def assert_generation_error(self, **kwargs):
        with self.assertRaises(
            content_plan_service.ContentPlanGenerationError
        ) as context:
            self.run_generation(**kwargs)

        return str(context.exception)

    def test_all_providers_use_the_same_product_contract(self):
        self.assertIs(
            content_plan_openai_service.CONTENT_PLAN_AI_CONTRACT,
            content_plan_service.CONTENT_PLAN_AI_CONTRACT,
        )
        self.assertIs(
            content_plan_gemini.GEMINI_CONTENT_PLAN_INSTRUCTIONS,
            content_plan_service.CONTENT_PLAN_AI_CONTRACT,
        )
        self.assertIs(
            content_plan_groq.CONTENT_PLAN_AI_CONTRACT,
            content_plan_service.CONTENT_PLAN_AI_CONTRACT,
        )

    def test_success_uses_groq_key_and_required_parameters(self):
        result, captured = self.run_generation(
            output_text=make_plan_json()
        )

        self.assertIsInstance(result, SevenDayContentPlan)
        self.assertEqual(
            [item.day for item in result.days],
            list(range(1, 8)),
        )
        self.assertEqual(
            captured["client"],
            {"api_key": "test-groq-key"},
        )
        self.assertEqual(
            captured["model"],
            "openai/gpt-oss-120b",
        )
        self.assertEqual(captured["reasoning_effort"], "low")
        self.assertEqual(
            captured["messages"],
            [
                {
                    "role": "system",
                    "content": (
                        content_plan_service.CONTENT_PLAN_AI_CONTRACT
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Краткий бриф пользователя:\n"
                        "Тестовый бриф"
                    ),
                },
            ],
        )
        self.assertEqual(
            captured["response_format"],
            {
                "type": "json_schema",
                "json_schema": {
                    "name": "seven_day_content_plan",
                    "strict": True,
                    "schema": SevenDayContentPlan.model_json_schema(),
                },
            },
        )

    def test_shared_contract_includes_product_safety_rules(self):
        contract = content_plan_service.CONTENT_PLAN_AI_CONTRACT.lower()

        for fragment in (
            "ровно на семь дней",
            "строго от 1 до 7",
            "подтверждённые факты о клиенте",
            "общие знания",
            "не существующим свойством бизнеса",
            "key_message должен содержать",
            "скидок",
            "промокодов",
            "адресов",
            "контактов",
            "часов работы",
            "отзывов",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, contract)

    def test_missing_api_key_raises_generation_error(self):
        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            with self.assertRaisesRegex(
                content_plan_service.ContentPlanGenerationError,
                "авторизоваться в Groq",
            ):
                content_plan_groq.generate_groq_content_plan(
                    "Тестовый бриф"
                )

    def test_invalid_json_or_invalid_schema_raises_generation_error(self):
        for output_text in (
            "{повреждённый json",
            make_plan_json(range(1, 7)),
            make_plan_json(range(1, 9)),
        ):
            with self.subTest(output_text=output_text):
                message = self.assert_generation_error(
                    output_text=output_text
                )
                self.assertIn("неполный контент-план", message)

    def test_wrong_day_order_raises_generation_error(self):
        message = self.assert_generation_error(
            output_text=make_plan_json(
                [1, 2, 4, 3, 5, 6, 7]
            )
        )

        self.assertIn("дни в неверном порядке", message)

    def test_empty_output_raises_generation_error(self):
        for output_text in (None, "", "   "):
            with self.subTest(output_text=output_text):
                message = self.assert_generation_error(
                    output_text=output_text
                )
                self.assertIn("не сформировал контент-план", message)

    def test_expected_groq_errors_raise_generation_error(self):
        cases = (
            (FakeAuthenticationError("auth"), "авторизоваться в Groq"),
            (FakeRateLimitError("rate"), "ограничил число запросов"),
            (FakeAPITimeoutError("timeout"), "Groq сейчас не отвечает"),
            (FakeAPIConnectionError("connection"), "Groq сейчас не отвечает"),
            (FakeAPIStatusError("status"), "Groq вернул ошибку сервиса"),
            (FakeGroqError("generic"), "получить ответ Groq"),
        )

        for error, expected_message in cases:
            with self.subTest(error=error):
                message = self.assert_generation_error(
                    create_error=error
                )
                self.assertIn(expected_message, message)

    def test_unexpected_runtime_error_is_not_masked(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "Programming error",
        ):
            self.run_generation(
                create_error=RuntimeError("Programming error")
            )


if __name__ == "__main__":
    unittest.main()
