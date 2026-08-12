import os
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from services import write_post as write_post_service
from services import write_post_gemini
from services import write_post_groq


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


class GroqWritePostTests(unittest.TestCase):
    def run_generation(
        self,
        output_text="Готовый пост",
        create_error=None,
        client_ai_context=(
            "Название или имя клиента: Иван Иванов\n"
            "Instagram клиента: @ivan\n"
            "Информация о клиенте: Семейная кофейня"
        ),
        topic="Как выбрать кофе",
        style="Экспертный",
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
            result = write_post_groq.generate_groq_post(
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

    def test_gemini_and_groq_use_the_same_product_contract(self):
        self.assertIs(
            write_post_gemini.WRITE_POST_INSTRUCTIONS,
            write_post_service.WRITE_POST_AI_CONTRACT,
        )
        self.assertIs(
            write_post_groq.WRITE_POST_AI_CONTRACT,
            write_post_service.WRITE_POST_AI_CONTRACT,
        )

    def test_generation_uses_key_model_reasoning_and_input(self):
        result, captured = self.run_generation()

        self.assertEqual(result, "Готовый пост")
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
                        write_post_service.WRITE_POST_AI_CONTRACT
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Контекст клиента:\n"
                        "Название или имя клиента: Иван Иванов\n"
                        "Instagram клиента: @ivan\n"
                        "Информация о клиенте: Семейная кофейня\n\n"
                        "Тема поста:\nКак выбрать кофе\n\n"
                        "Стиль поста:\nЭкспертный"
                    ),
                },
            ],
        )

    def test_contract_contains_shared_safety_and_style_rules(self):
        contract = write_post_service.WRITE_POST_AI_CONTRACT.lower()

        for fragment in (
            "готовый smm-пост на русском языке",
            "экспертный, продающий, дружелюбный или информационный",
            "подтверждённые факты о клиенте",
            "скидки",
            "промокоды",
            "адреса",
            "контакты",
            "часы работы",
            "отзывы",
            "общие знания",
            "не добавляй их в текст",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, contract)

    def test_generation_without_client_uses_neutral_context(self):
        _, captured = self.run_generation(
            client_ai_context="",
            topic="Тема без клиента",
            style="Дружелюбный",
        )

        input_text = captured["messages"][1]["content"]
        self.assertIn("Контекст клиента:\nНе указан.", input_text)
        self.assertIn("Тема поста:\nТема без клиента", input_text)
        self.assertIn("Стиль поста:\nДружелюбный", input_text)

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
                self.assertIn("не сформировал текст поста", message)

    def test_missing_api_key_raises_generation_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(
                write_post_service.WritePostGenerationError,
                "авторизоваться в Groq",
            ):
                write_post_groq.generate_groq_post(
                    "",
                    "Тема",
                    "Информационный",
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
        with self.assertRaisesRegex(
            RuntimeError,
            "Programming error",
        ):
            self.run_generation(
                create_error=RuntimeError("Programming error")
            )


class GroqWritePostServiceTests(unittest.TestCase):
    def setUp(self):
        self.client_context = {
            "name": " Иван ",
            "last_name": " Иванов ",
            "phone": "+372 5555 0000",
            "instagram": " @ivan ",
            "email": "ivan@example.com",
            "notes": " Семейная кофейня ",
        }

    def test_safe_context_excludes_phone_and_email(self):
        context = write_post_service.build_client_ai_context(
            self.client_context
        )

        self.assertNotIn("+372 5555 0000", context)
        self.assertNotIn("ivan@example.com", context)

    def test_success_creates_post_and_saves_once(self):
        existing_posts = [
            {
                "id": 4,
                "client": "Старый клиент",
                "client_context": None,
                "topic": "Старая тема",
                "style": "Информационный",
                "text": "Старый текст",
            }
        ]
        save_posts = Mock()

        with (
            patch.object(
                write_post_groq,
                "generate_groq_post",
                return_value="AI-текст",
            ) as generate_post,
            patch.object(
                write_post_service.posts_storage,
                "load_posts",
                return_value=existing_posts,
            ),
            patch.object(
                write_post_service.posts_storage,
                "save_posts",
                save_posts,
            ),
        ):
            post = write_post_service.create_and_save_groq_post(
                "Иван Иванов",
                self.client_context,
                "Как выбрать кофе",
                "Экспертный",
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
                "id": 5,
                "client": "Иван Иванов",
                "client_context": self.client_context,
                "topic": "Как выбрать кофе",
                "style": "Экспертный",
                "text": "AI-текст",
            },
        )
        save_posts.assert_called_once_with(existing_posts)

    def test_generation_error_does_not_load_or_save_posts(self):
        error = write_post_service.WritePostGenerationError(
            "Groq недоступен"
        )

        with (
            patch.object(
                write_post_groq,
                "generate_groq_post",
                side_effect=error,
            ),
            patch.object(
                write_post_service.posts_storage, "load_posts"
            ) as load_posts,
            patch.object(
                write_post_service.posts_storage, "save_posts"
            ) as save_posts,
        ):
            with self.assertRaises(
                write_post_service.WritePostGenerationError
            ) as context:
                write_post_service.create_and_save_groq_post(
                    "Иван Иванов",
                    self.client_context,
                    "Как выбрать кофе",
                    "Экспертный",
                )

        self.assertIs(context.exception, error)
        load_posts.assert_not_called()
        save_posts.assert_not_called()


if __name__ == "__main__":
    unittest.main()
