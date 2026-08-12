import json
import os
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from models.post_idea import GeneratedPostIdeas
from services import post_ideas as post_ideas_service
from services import post_ideas_gemini
from services import post_ideas_groq


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


def make_ideas_json(ideas=None):
    if ideas is None:
        ideas = [
            "Как выбрать кофе для дома",
            "Пять ошибок при заказе кофе",
            "Как хранить кофейные зёрна",
        ]

    return json.dumps({"ideas": ideas}, ensure_ascii=False)


class GroqPostIdeasTests(unittest.TestCase):
    def run_generation(
        self,
        output_text=None,
        create_error=None,
        client_ai_context=(
            "Название или имя клиента: Иван Иванов\n"
            "Instagram клиента: @ivan\n"
            "Информация о клиенте: Семейная кофейня"
        ),
        brief="Идеи для кофейни",
        existing_ideas=None,
    ):
        if output_text is None:
            output_text = make_ideas_json()

        if existing_ideas is None:
            existing_ideas = [
                "💡 История появления эспрессо",
                "💡 Разница между арабикой и робустой",
            ]

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
            result = post_ideas_groq.generate_groq_post_ideas(
                client_ai_context,
                brief,
                existing_ideas,
            )

        return result, captured

    def assert_generation_error(self, **kwargs):
        with self.assertRaises(
            post_ideas_service.PostIdeasGenerationError
        ) as context:
            self.run_generation(**kwargs)

        return str(context.exception)

    def test_gemini_and_groq_use_the_same_product_contract(self):
        self.assertIs(
            post_ideas_gemini.POST_IDEAS_INSTRUCTIONS,
            post_ideas_service.POST_IDEAS_AI_CONTRACT,
        )
        self.assertIs(
            post_ideas_groq.POST_IDEAS_AI_CONTRACT,
            post_ideas_service.POST_IDEAS_AI_CONTRACT,
        )

    def test_generation_uses_key_schema_and_equal_input_context(self):
        result, captured = self.run_generation()

        self.assertIsInstance(result, GeneratedPostIdeas)
        self.assertEqual(
            captured["client"],
            {"api_key": "test-groq-key"},
        )
        self.assertEqual(
            captured["model"], "openai/gpt-oss-120b")
        self.assertEqual(captured["reasoning_effort"], "low")
        self.assertEqual(
            captured["response_format"],
            {
                "type": "json_schema",
                "json_schema": {
                    "name": "generated_post_ideas",
                    "strict": True,
                    "schema": GeneratedPostIdeas.model_json_schema(),
                },
            },
        )
        self.assertIs(
            captured["messages"][0]["content"],
            post_ideas_service.POST_IDEAS_AI_CONTRACT,
        )
        input_text = captured["messages"][1]["content"]
        self.assertIn(
            "Контекст клиента:\nНазвание или имя клиента: Иван Иванов",
            input_text,
        )
        self.assertIn(
            "Бриф или тема пользователя:\nИдеи для кофейни",
            input_text,
        )
        self.assertIn(
            "1. 💡 История появления эспрессо\n"
            "2. 💡 Разница между арабикой и робустой",
            input_text,
        )

    def test_shared_contract_contains_product_safety_rules(self):
        contract = post_ideas_service.POST_IDEAS_AI_CONTRACT.lower()

        for fragment in (
            "ровно три разные самостоятельные",
            "на русском языке",
            "не повторяй существующие идеи",
            "смысловые дубли",
            "подтверждённые факты о клиенте",
            "скидки",
            "промокоды",
            "адреса",
            "контакты",
            "часы работы",
            "отзывы",
            "общие знания",
            "а не достраивай детали",
            "не готовым длинным текстом поста",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, contract)

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

    def test_empty_or_invalid_output_raises_generation_error(self):
        for output_text in (
            "",
            "   ",
            "{повреждённый json",
            make_ideas_json(["Первая", "Вторая"]),
            make_ideas_json(["Первая", "   ", "Третья"]),
        ):
            with self.subTest(output_text=output_text):
                message = self.assert_generation_error(
                    output_text=output_text
                )
                self.assertTrue(
                    "не сформировал идеи" in message
                    or "некорректный список идей" in message
                )

    def test_missing_api_key_raises_generation_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(
                post_ideas_service.PostIdeasGenerationError,
                "авторизоваться в Groq",
            ):
                post_ideas_groq.generate_groq_post_ideas(
                    "",
                    "Бриф",
                    [],
                )

    def test_expected_groq_errors_are_mapped(self):
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
        with self.assertRaisesRegex(RuntimeError, "Programming error"):
            self.run_generation(
                create_error=RuntimeError("Programming error")
            )


class GroqPostIdeasServiceTests(unittest.TestCase):
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
                "save_all_post_ideas",
            ) as save_post_ideas,
            patch.object(
                post_ideas_groq,
                "generate_groq_post_ideas",
                return_value=generated,
            ) as generate_ideas,
        ):
            result = (
                post_ideas_service.generate_groq_post_idea_candidates(
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


if __name__ == "__main__":
    unittest.main()
