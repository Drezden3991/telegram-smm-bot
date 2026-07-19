import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers import content_plan


def make_plan():
    return content_plan.SevenDayContentPlan(
        days=[
            content_plan.ContentPlanDay(
                day=day,
                goal=f"Цель {day}",
                topic=f"Тема {day}",
                format="Текстовый пост",
                key_message=f"Ключевой тезис {day}",
                cta=f"Действие {day}",
            )
            for day in range(1, 8)
        ]
    )


class FakeMessage:
    def __init__(self, text):
        self.text = text
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs))


class FakeState:
    def __init__(self):
        self.cleared = False

    async def clear(self):
        self.cleared = True


class ContentPlanTests(unittest.TestCase):
    def test_generation_uses_required_responses_parameters(self):
        parsed_plan = make_plan()
        fake_responses = SimpleNamespace()
        captured = {}

        def parse(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(output_parsed=parsed_plan)

        fake_responses.parse = parse
        fake_client = SimpleNamespace(responses=fake_responses)

        with patch("handlers.content_plan.OpenAI", return_value=fake_client):
            result = content_plan.generate_ai_content_plan("Тестовый бриф")

        self.assertEqual(result, parsed_plan)
        self.assertEqual(captured["model"], "gpt-5.6")
        self.assertEqual(captured["reasoning"], {"effort": "low"})
        self.assertIs(captured["text_format"], content_plan.SevenDayContentPlan)

    def test_formatter_contains_all_seven_days_and_fields(self):
        result = content_plan.format_content_plan_text("Тестовый бриф", make_plan())

        self.assertLessEqual(len(result), 4096)
        for day in range(1, 8):
            self.assertIn(f"День {day}", result)
        for label in ["Цель:", "Тема:", "Формат:", "Ключевой тезис:", "CTA:"]:
            self.assertIn(label, result)

    def test_maximum_structured_output_fits_telegram_message(self):
        maximum_plan = content_plan.SevenDayContentPlan(
            days=[
                content_plan.ContentPlanDay(
                    day=day,
                    goal="Ц" * 50,
                    topic="Т" * 90,
                    format="Ф" * 30,
                    key_message="К" * 120,
                    cta="П" * 70,
                )
                for day in range(1, 8)
            ]
        )

        result = content_plan.format_content_plan_text(
            "Б" * content_plan.MAX_BRIEF_LENGTH,
            maximum_plan,
        )

        self.assertLessEqual(len(result), 4096)

    def test_invalid_day_order_is_rejected(self):
        invalid_plan = make_plan()
        invalid_plan.days[0].day = 2
        fake_client = SimpleNamespace(
            responses=SimpleNamespace(
                parse=lambda **kwargs: SimpleNamespace(output_parsed=invalid_plan)
            )
        )

        with patch("handlers.content_plan.OpenAI", return_value=fake_client):
            with self.assertRaises(content_plan.ContentPlanGenerationError):
                content_plan.generate_ai_content_plan("Тестовый бриф")


class ContentPlanHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_api_error_does_not_save_content_plan(self):
        message = FakeMessage("Ниша: кофе; аудитория: жители города; цель: продажи")
        state = FakeState()

        with (
            patch(
                "handlers.content_plan.build_content_plan_text",
                new=AsyncMock(
                    side_effect=content_plan.ContentPlanGenerationError(
                        "OpenAI сейчас не отвечает."
                    )
                ),
            ),
            patch("handlers.content_plan.save_content_plans") as save_content_plans,
        ):
            await content_plan.create_content_plan(message, state)

        save_content_plans.assert_not_called()
        self.assertTrue(state.cleared)
        self.assertIn("OpenAI сейчас не отвечает.", message.answers[-1][0])


if __name__ == "__main__":
    unittest.main()
