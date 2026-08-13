from types import SimpleNamespace
import unittest
from unittest.mock import patch

from services import write_post as write_post_service
from services import write_post_openai


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


class OpenAIWritePostTests(unittest.TestCase):
    def run_generation(self, output_text="Готовый пост", error=None):
        captured = {}

        class FakeResponses:
            def create(self, **kwargs):
                captured.update(kwargs)

                if error:
                    raise error

                return SimpleNamespace(output_text=output_text)

        class FakeClient:
            def __init__(self, **kwargs):
                captured["client"] = kwargs
                self.responses = FakeResponses()

        with patch.multiple(
            write_post_openai,
            OpenAI=FakeClient,
            OpenAIError=FakeOpenAIError,
            AuthenticationError=FakeAuthenticationError,
            RateLimitError=FakeRateLimitError,
            APITimeoutError=FakeAPITimeoutError,
            APIConnectionError=FakeAPIConnectionError,
            APIStatusError=FakeAPIStatusError,
        ):
            result = write_post_openai.generate_openai_post(
                "Название или имя клиента: Coffee Lab",
                "Почему стоит попробовать specialty coffee",
                "Дружелюбный",
            )

        return result, captured

    def assert_generation_error(self, error):
        with self.assertRaises(
            write_post_service.WritePostGenerationError
        ) as context:
            self.run_generation(error=error)

        return str(context.exception)

    def test_success_uses_openai_contract_and_strips_text(self):
        result, captured = self.run_generation("  Готовый пост\n")

        self.assertEqual(result, "Готовый пост")
        self.assertEqual(
            captured["client"],
            {"timeout": 45.0, "max_retries": 1},
        )
        self.assertEqual(captured["model"], "gpt-5.6")
        self.assertEqual(captured["reasoning"]["effort"], "low")
        self.assertEqual(
            captured["input"][0]["content"],
            write_post_service.WRITE_POST_AI_CONTRACT,
        )
        self.assertIn(
            "Coffee Lab",
            captured["input"][1]["content"],
        )

    def test_empty_output_is_a_generation_error(self):
        for output_text in (None, "", "   "):
            with self.subTest(output_text=output_text):
                with self.assertRaisesRegex(
                    write_post_service.WritePostGenerationError,
                    "не сформировал текст поста",
                ):
                    self.run_generation(output_text=output_text)

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
                    self.assert_generation_error(error),
                )

    def test_unexpected_runtime_error_is_not_masked(self):
        with self.assertRaisesRegex(RuntimeError, "programming"):
            self.run_generation(error=RuntimeError("programming"))
