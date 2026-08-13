from types import SimpleNamespace
import unittest
from unittest.mock import patch

from models.post_idea import GeneratedPostIdeas
from services import post_ideas as post_ideas_service
from services import post_ideas_openai


class FakeOpenAIError(Exception):
    pass


class FakeAuthenticationError(FakeOpenAIError):
    pass


class FakeRateLimitError(FakeOpenAIError):
    pass


class FakeAPITimeoutError(FakeOpenAIError):
    pass


class FakeAPIConnectionError(FakeOpenAIError):
    pass


class FakeAPIStatusError(FakeOpenAIError):
    pass


class OpenAIPostIdeasTests(unittest.TestCase):
    _default_ideas = object()

    def run_generation(
        self,
        generated_ideas=_default_ideas,
        error=None,
    ):
        captured = {}

        if generated_ideas is self._default_ideas:
            generated_ideas = GeneratedPostIdeas(
                ideas=["Первая идея", "Вторая идея", "Третья идея"]
            )

        class FakeResponses:
            def parse(self, **kwargs):
                captured.update(kwargs)

                if error:
                    raise error

                return SimpleNamespace(output_parsed=generated_ideas)

        class FakeClient:
            def __init__(self, **kwargs):
                captured["client"] = kwargs
                self.responses = FakeResponses()

        with patch.multiple(
            post_ideas_openai,
            OpenAI=FakeClient,
            OpenAIError=FakeOpenAIError,
            AuthenticationError=FakeAuthenticationError,
            RateLimitError=FakeRateLimitError,
            APITimeoutError=FakeAPITimeoutError,
            APIConnectionError=FakeAPIConnectionError,
            APIStatusError=FakeAPIStatusError,
        ):
            result = post_ideas_openai.generate_openai_post_ideas(
                "Название или имя клиента: Coffee Lab",
                "Идеи для знакомства с кофейней",
                ["💡 Что такое specialty coffee"],
            )

        return result, captured

    def assert_generation_error(self, **kwargs):
        with self.assertRaises(
            post_ideas_service.PostIdeasGenerationError
        ) as context:
            self.run_generation(**kwargs)

        return str(context.exception)

    def test_success_uses_structured_output_and_shared_contract(self):
        result, captured = self.run_generation()

        self.assertEqual(len(result.ideas), 3)
        self.assertEqual(captured["model"], "gpt-5.6")
        self.assertEqual(captured["reasoning"]["effort"], "low")
        self.assertIs(captured["text_format"], GeneratedPostIdeas)
        self.assertEqual(
            captured["input"][0]["content"],
            post_ideas_service.POST_IDEAS_AI_CONTRACT,
        )
        self.assertIn("Coffee Lab", captured["input"][1]["content"])
        self.assertIn(
            "specialty coffee",
            captured["input"][1]["content"],
        )

    def test_missing_or_invalid_candidates_are_generation_errors(self):
        cases = (
            None,
            SimpleNamespace(ideas=["Первая", "Вторая", ""]),
            SimpleNamespace(ideas=["Первая", "Вторая"]),
        )

        for generated_ideas in cases:
            with self.subTest(generated_ideas=generated_ideas):
                self.assertIn(
                    "некорректный список идей"
                    if generated_ideas is not None
                    else "не сформировал идеи",
                    self.assert_generation_error(
                        generated_ideas=generated_ideas,
                    ),
                )

    def test_schema_validation_error_is_a_generation_error(self):
        self.assertIn(
            "некорректный список идей",
            self.assert_generation_error(
                error=ValueError("invalid schema"),
            ),
        )

    def test_expected_openai_errors_are_mapped(self):
        cases = (
            (FakeAuthenticationError("auth"), "авторизоваться"),
            (FakeRateLimitError("rate"), "ограничил число запросов"),
            (FakeAPITimeoutError("timeout"), "сейчас не отвечает"),
            (FakeAPIConnectionError("connection"), "сейчас не отвечает"),
            (FakeAPIStatusError("status"), "ошибку сервиса"),
            (FakeOpenAIError("api"), "получить ответ OpenAI"),
        )

        for error, expected in cases:
            with self.subTest(error=error):
                self.assertIn(
                    expected,
                    self.assert_generation_error(error=error),
                )

    def test_unexpected_runtime_error_is_not_masked(self):
        with self.assertRaisesRegex(RuntimeError, "programming"):
            self.run_generation(error=RuntimeError("programming"))
