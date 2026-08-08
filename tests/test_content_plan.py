import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiogram.filters import StateFilter

from handlers import content_plan, post_ideas, write_post


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


def make_stored_plan(client_name="", brief="Продвижение кофейни"):
    client_line = f"Клиент: {client_name}\n" if client_name else ""

    return (
        "📅 AI-контент-план на 7 дней\n\n"
        f"{client_line}"
        f"Бриф: {brief}\n\n"
        "День 1\n"
        "🎯 Цель: Познакомить аудиторию с продуктом"
    )


class FakeMessage:
    def __init__(self, text):
        self.text = text
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs))


class FakeState:
    def __init__(self, data=None, state=None):
        self.data = dict(data or {})
        self.state = state
        self.cleared = False

    async def get_data(self):
        return dict(self.data)

    async def update_data(self, data=None, **kwargs):
        if data:
            self.data.update(data)

        self.data.update(kwargs)
        return dict(self.data)

    async def set_state(self, state):
        self.state = state

    async def clear(self):
        self.data.clear()
        self.state = None
        self.cleared = True


def get_state_filter(router, callback):
    handler = next(
        handler
        for handler in router.message.handlers
        if handler.callback is callback
    )

    return next(
        filter_object.callback
        for filter_object in handler.filters
        if isinstance(filter_object.callback, StateFilter)
    )


class ContentPlanStorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)

        self.content_plans_file = Path(
            self.temporary_directory.name
        ) / "content_plans.txt"

        self.file_patches = ExitStack()
        self.addCleanup(self.file_patches.close)
        self.file_patches.enter_context(
            patch.object(
                content_plan,
                "CONTENT_PLANS_FILE",
                str(self.content_plans_file),
            )
        )

        storage_module = getattr(
            content_plan,
            "content_plans_storage",
            None,
        )

        if storage_module is not None:
            self.file_patches.enter_context(
                patch.object(
                    storage_module,
                    "CONTENT_PLANS_FILE",
                    str(self.content_plans_file),
                )
            )

    def test_read_returns_empty_for_missing_file(self):
        self.assertEqual(content_plan.read_content_plans(), [])

    def test_read_returns_empty_for_empty_file(self):
        self.content_plans_file.write_text("", encoding="utf-8")

        self.assertEqual(content_plan.read_content_plans(), [])

    def test_read_returns_empty_for_whitespace_only_file(self):
        self.content_plans_file.write_text(
            "  \n\t\n  ",
            encoding="utf-8",
        )

        self.assertEqual(content_plan.read_content_plans(), [])

    def test_read_multiple_plans_separated_by_separator(self):
        separator = content_plan.SEPARATOR
        self.content_plans_file.write_text(
            f"План 1\n{separator}\nПлан 2\n{separator}\n",
            encoding="utf-8",
        )

        self.assertEqual(
            content_plan.read_content_plans(),
            ["План 1", "План 2"],
        )

    def test_read_ignores_empty_fragments(self):
        separator = content_plan.SEPARATOR
        self.content_plans_file.write_text(
            (
                f"{separator}\n"
                f"План 1\n{separator}\n"
                f"{separator}\n"
                f"План 2\n{separator}\n"
            ),
            encoding="utf-8",
        )

        self.assertEqual(
            content_plan.read_content_plans(),
            ["План 1", "План 2"],
        )

    def test_save_uses_exact_forty_hyphen_separator(self):
        content_plan.save_content_plans(["План"])

        separator = "-" * 40
        self.assertEqual(content_plan.SEPARATOR, separator)
        self.assertEqual(
            self.content_plans_file.read_text(encoding="utf-8"),
            f"План\n{separator}\n",
        )

    def test_save_strips_outer_whitespace_from_each_plan(self):
        content_plan.save_content_plans(
            [" \nПлан 1\n ", "\tПлан 2\t"]
        )

        separator = content_plan.SEPARATOR
        self.assertEqual(
            self.content_plans_file.read_text(encoding="utf-8"),
            (
                f"План 1\n{separator}\n"
                f"План 2\n{separator}\n"
            ),
        )

    def test_save_adds_trailing_separator_after_last_plan(self):
        content_plan.save_content_plans(["Последний план"])

        saved_content = self.content_plans_file.read_text(
            encoding="utf-8"
        )
        self.assertTrue(
            saved_content.endswith(
                f"{content_plan.SEPARATOR}\n"
            )
        )

    def test_save_empty_list_clears_file(self):
        self.content_plans_file.write_text(
            "Старые данные",
            encoding="utf-8",
        )

        content_plan.save_content_plans([])

        self.assertEqual(
            self.content_plans_file.read_text(encoding="utf-8"),
            "",
        )

    def test_saved_plans_can_be_read_without_changes(self):
        plans = [
            "План 1\nВторая строка",
            "План 2\nЕщё одна строка",
        ]

        content_plan.save_content_plans(plans)

        self.assertEqual(
            content_plan.read_content_plans(),
            plans,
        )


class ContentPlanSharedStorageCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)

        temporary_path = Path(self.temporary_directory.name)
        self.clients_file = temporary_path / "clients.txt"
        self.post_ideas_file = temporary_path / "post_ideas.txt"

        self.file_patches = ExitStack()
        self.addCleanup(self.file_patches.close)

        self._patch_file_path(
            "CLIENTS_FILE",
            "clients_storage",
            self.clients_file,
        )
        self._patch_file_path(
            "POST_IDEAS_FILE",
            "post_ideas_storage",
            self.post_ideas_file,
        )

    def _patch_file_path(
        self,
        handler_attribute,
        storage_attribute,
        file_path,
    ):
        if hasattr(content_plan, handler_attribute):
            self.file_patches.enter_context(
                patch.object(
                    content_plan,
                    handler_attribute,
                    str(file_path),
                )
            )

        storage_module = getattr(
            content_plan,
            storage_attribute,
            None,
        )

        if storage_module is not None:
            self.file_patches.enter_context(
                patch.object(
                    storage_module,
                    handler_attribute,
                    str(file_path),
                )
            )

    def test_create_client_from_current_six_field_format(self):
        client = content_plan.create_client_from_line(
            "Иван | Иванов | +372 | @ivan | "
            "ivan@example.com | Постоянный клиент"
        )

        self.assertEqual(
            client,
            {
                "name": "Иван",
                "last_name": "Иванов",
                "phone": "+372",
                "instagram": "@ivan",
                "email": "ivan@example.com",
                "notes": "Постоянный клиент",
            },
        )

    def test_create_client_from_legacy_five_field_format(self):
        client = content_plan.create_client_from_line(
            "Анна | +372 | @anna | "
            "anna@example.com | Старый формат"
        )

        self.assertEqual(
            client,
            {
                "name": "Анна",
                "last_name": "",
                "phone": "+372",
                "instagram": "@anna",
                "email": "anna@example.com",
                "notes": "Старый формат",
            },
        )

    def test_load_clients_preserves_current_file_behavior(self):
        self.clients_file.write_text(
            (
                "Иван | Иванов | +372 | @ivan | "
                "ivan@example.com | Новый формат\n"
                "Анна | +371 | @anna | "
                "anna@example.com | Старый формат\n"
            ),
            encoding="utf-8",
        )

        self.assertEqual(
            content_plan.load_clients(),
            [
                {
                    "name": "Иван",
                    "last_name": "Иванов",
                    "phone": "+372",
                    "instagram": "@ivan",
                    "email": "ivan@example.com",
                    "notes": "Новый формат",
                },
                {
                    "name": "Анна",
                    "last_name": "",
                    "phone": "+371",
                    "instagram": "@anna",
                    "email": "anna@example.com",
                    "notes": "Старый формат",
                },
            ],
        )

    def test_load_clients_returns_empty_for_missing_file(self):
        self.assertEqual(content_plan.load_clients(), [])

    def test_load_clients_skips_blank_lines(self):
        self.clients_file.write_text(
            (
                "\n   \n"
                "Иван | Иванов | +372 | @ivan | "
                "ivan@example.com | Заметка\n"
                "\t\n"
            ),
            encoding="utf-8",
        )

        loaded_clients = content_plan.load_clients()

        self.assertEqual(len(loaded_clients), 1)
        self.assertEqual(loaded_clients[0]["name"], "Иван")

    def test_load_post_ideas_preserves_current_line_format(self):
        self.post_ideas_file.write_text(
            "  💡 Первая идея  \nВторая идея\n",
            encoding="utf-8",
        )

        self.assertEqual(
            content_plan.load_post_ideas(),
            ["💡 Первая идея", "Вторая идея"],
        )

    def test_load_post_ideas_returns_empty_for_missing_file(self):
        self.assertEqual(content_plan.load_post_ideas(), [])

    def test_load_post_ideas_skips_blank_lines(self):
        self.post_ideas_file.write_text(
            "\n   \nИдея\n\t\n",
            encoding="utf-8",
        )

        self.assertEqual(
            content_plan.load_post_ideas(),
            ["Идея"],
        )


class ContentPlanSelectionAndFormattingTests(unittest.TestCase):
    def test_get_client_full_name_strips_and_joins_parts(self):
        client = {
            "name": "  Иван  ",
            "last_name": "  Иванов  ",
        }

        self.assertEqual(
            content_plan.get_client_full_name(client),
            "Иван Иванов",
        )

    def test_get_client_full_name_handles_empty_data(self):
        self.assertEqual(
            content_plan.get_client_full_name({}),
            "",
        )
        self.assertEqual(
            content_plan.get_client_full_name(
                {"name": "", "last_name": "  Петров  "}
            ),
            "Петров",
        )

    def test_get_selected_client_returns_exact_numbered_match(self):
        clients = [
            {"name": "Анна", "last_name": "Смирнова"},
            {"name": "Иван", "last_name": "Иванов"},
        ]

        selected_client = content_plan.get_selected_client(
            "2. Иван Иванов",
            clients,
        )

        self.assertIs(selected_client, clients[1])

    def test_get_selected_client_rejects_nonexact_or_empty_choice(self):
        clients = [
            {"name": "Иван", "last_name": "Иванов"},
        ]

        self.assertIsNone(
            content_plan.get_selected_client(
                "1. иван иванов",
                clients,
            )
        )
        self.assertIsNone(
            content_plan.get_selected_client(
                "1. Иван Иванов",
                [],
            )
        )

    def test_get_selected_idea_number_accepts_current_button_marks(self):
        self.assertEqual(
            content_plan.get_selected_idea_number("▫️ 2", 3),
            2,
        )
        self.assertEqual(
            content_plan.get_selected_idea_number("✅ 3", 3),
            3,
        )

    def test_get_selected_idea_number_rejects_invalid_choices(self):
        invalid_choices = (
            "",
            "2",
            "🔹 2",
            "▫️ два",
            "▫️ 0",
            "▫️ 4",
        )

        for choice in invalid_choices:
            with self.subTest(choice=choice):
                self.assertIsNone(
                    content_plan.get_selected_idea_number(
                        choice,
                        3,
                    )
                )

    def test_format_numbered_ideas_preserves_order_and_numbering(self):
        result = content_plan.format_numbered_ideas(
            ["Первая идея", "Вторая идея", "Третья идея"]
        )

        self.assertEqual(
            result,
            (
                "1. Первая идея\n"
                "2. Вторая идея\n"
                "3. Третья идея"
            ),
        )

    def test_format_numbered_ideas_returns_empty_string_for_empty_list(self):
        self.assertEqual(
            content_plan.format_numbered_ideas([]),
            "",
        )

    def test_format_selected_ideas_uses_source_order_and_numbers(self):
        result = content_plan.format_selected_ideas(
            ["Первая идея", "Вторая идея", "Третья идея"],
            ["Третья идея", "Первая идея"],
        )

        self.assertEqual(
            result,
            (
                "✅ Выбрано:\n\n"
                "1. Первая идея\n"
                "3. Третья идея"
            ),
        )

    def test_format_selected_ideas_uses_empty_selection_text(self):
        expected_text = (
            "✅ Выбрано:\n\n"
            "Пока ничего не выбрано."
        )

        self.assertEqual(
            content_plan.format_selected_ideas(
                ["Первая идея"],
                [],
            ),
            expected_text,
        )
        self.assertEqual(
            content_plan.format_selected_ideas(
                ["Первая идея"],
                ["Отсутствующая идея"],
            ),
            expected_text,
        )


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
        result = content_plan.format_content_plan_text(
            None,
            [],
            "Тестовый бриф",
            make_plan(),
        )

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
            None,
            [],
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

    def test_selected_ideas_are_added_to_ai_brief(self):
        selected_ideas = [
            "Разбор частой ошибки",
            "История клиента",
        ]

        result = content_plan.build_ai_brief(
            None,
            selected_ideas,
            "Продвижение кофейни",
        )

        self.assertIn("Сохранённые идеи постов:", result)
        self.assertIn("1. Разбор частой ошибки", result)
        self.assertIn("2. История клиента", result)
        self.assertIn("Задача пользователя:\nПродвижение кофейни", result)

    def test_selected_ideas_are_shown_in_formatted_plan(self):
        selected_ideas = ["Разбор частой ошибки"]

        result = content_plan.format_content_plan_text(
            None,
            selected_ideas,
            "Продвижение кофейни",
            make_plan(),
        )

        self.assertIn("Выбранные идеи:\n1. Разбор частой ошибки", result)

    def test_empty_selected_ideas_do_not_add_ideas_block(self):
        result = content_plan.format_content_plan_text(
            None,
            [],
            "Продвижение кофейни",
            make_plan(),
        )

        self.assertNotIn("Выбранные идеи:", result)

    def test_idea_menu_uses_only_compact_number_buttons(self):
        long_idea = "Очень длинная идея " * 30

        menu = content_plan.create_ideas_menu(
            [long_idea, "Короткая идея"],
            [long_idea],
        )
        button_texts = [
            button.text
            for row in menu.keyboard
            for button in row
        ]

        self.assertEqual(button_texts[:2], ["✅ 1", "▫️ 2"])
        self.assertEqual(
            button_texts[-3:],
            [
                content_plan.FINISH_IDEAS_BUTTON,
                content_plan.SKIP_IDEAS_BUTTON,
                content_plan.BACK_BUTTON,
            ],
        )
        self.assertNotIn(long_idea, button_texts)

    def test_idea_number_matches_its_position_in_list(self):
        ideas = [
            "Первая идея",
            "Вторая идея",
            "Третья идея",
        ]

        selected_number = content_plan.get_selected_idea_number(
            "▫️ 2",
            len(ideas),
        )

        self.assertEqual(selected_number, 2)
        self.assertEqual(ideas[selected_number - 1], "Вторая идея")
        self.assertIsNone(
            content_plan.get_selected_idea_number(
                "▫️ 4",
                len(ideas),
            )
        )

    def test_numbered_idea_list_preserves_source_order(self):
        result = content_plan.format_numbered_ideas(
            [
                "Первая идея",
                "Вторая идея",
                "Третья идея",
            ]
        )

        self.assertEqual(
            result,
            "1. Первая идея\n2. Вторая идея\n3. Третья идея",
        )

    def test_short_title_contains_client_and_brief(self):
        result = content_plan.create_content_plan_short_title(
            make_stored_plan(
                client_name="Анна Смирнова",
                brief="Продвижение семейной кофейни",
            )
        )

        self.assertEqual(
            result,
            "Анна Смирнова — Продвижение семейной кофейни",
        )

    def test_short_title_uses_fallback_and_is_limited(self):
        result = content_plan.create_content_plan_short_title(
            make_stored_plan(brief="Очень длинный бриф " * 20)
        )

        self.assertTrue(result.startswith("Без клиента — Очень длинный бриф"))
        self.assertLessEqual(
            len(result),
            content_plan.CONTENT_PLAN_SHORT_TITLE_MAX_LENGTH,
        )
        self.assertTrue(result.endswith("…"))

    def test_compact_list_does_not_include_full_plan(self):
        result = content_plan.format_compact_content_plans_list(
            [
                make_stored_plan("Анна", "Кофейня"),
                make_stored_plan(brief="Онлайн-школа"),
            ]
        )

        self.assertIn("1. Анна — Кофейня", result)
        self.assertIn("2. Без клиента — Онлайн-школа", result)
        self.assertNotIn("День 1", result)
        self.assertNotIn("🎯 Цель:", result)

    def test_content_plan_number_menu_has_three_buttons_per_row(self):
        menu = content_plan.create_content_plan_number_menu(7)
        rows = [
            [button.text for button in row]
            for row in menu.keyboard
        ]

        self.assertEqual(
            rows,
            [
                ["1", "2", "3"],
                ["4", "5", "6"],
                ["7"],
                [content_plan.BACK_BUTTON],
            ],
        )

    def test_content_plan_number_accepts_only_current_button_number(self):
        self.assertEqual(
            content_plan.get_selected_content_plan_number("2", 3),
            2,
        )
        self.assertIsNone(
            content_plan.get_selected_content_plan_number("4", 3)
        )
        self.assertIsNone(
            content_plan.get_selected_content_plan_number("2. План", 3)
        )


class TelegramTextSplittingTests(unittest.TestCase):
    def test_text_shorter_than_limit_stays_in_one_chunk(self):
        text = "Короткий список контент-планов"

        chunks = content_plan.split_text_for_telegram(text)

        self.assertEqual(chunks, [text])

    def test_text_longer_than_limit_is_split(self):
        text = ("Строка контент-плана\n" * 300).strip()

        chunks = content_plan.split_text_for_telegram(text)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(chunks[0].endswith("\n"))

    def test_no_chunk_exceeds_telegram_limit(self):
        text = ("Слово " * 2000) + ("Д" * 5000)

        chunks = content_plan.split_text_for_telegram(text)

        self.assertTrue(chunks)
        self.assertTrue(
            all(
                len(chunk) <= content_plan.TELEGRAM_MESSAGE_LIMIT
                for chunk in chunks
            )
        )

    def test_joining_chunks_preserves_original_text(self):
        text = (
            "📋 Мои контент-планы:\n\n"
            + ("День 1\nЦель: тестовая цель\n\n" * 250)
            + "Введите номер контент-плана:"
        )

        chunks = content_plan.split_text_for_telegram(text)

        self.assertEqual("".join(chunks), text)


class ContentPlanHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_plan_list_returns_to_content_plan_menu(self):
        handlers = (
            content_plan.ask_delete_content_plan_number,
            content_plan.ask_edit_content_plan_number,
        )

        for handler in handlers:
            with self.subTest(handler=handler.__name__):
                message = FakeMessage("")
                state = FakeState()

                with patch(
                    "handlers.content_plan.read_content_plans",
                    return_value=[],
                ):
                    await handler(message, state)

                self.assertIn("пока нет", message.answers[-1][0])
                self.assertIs(
                    message.answers[-1][1]["reply_markup"],
                    content_plan.content_plan_menu,
                )

    async def test_delete_selection_shows_compact_list_and_number_buttons(self):
        plans = [
            make_stored_plan("Анна", "Кофейня"),
            make_stored_plan(brief="Онлайн-школа"),
        ]
        message = FakeMessage("")
        state = FakeState()

        with patch(
            "handlers.content_plan.read_content_plans",
            return_value=plans,
        ):
            await content_plan.ask_delete_content_plan_number(
                message,
                state,
            )

        self.assertEqual(
            state.state,
            content_plan.DeleteContentPlan.waiting_for_number,
        )
        self.assertEqual(state.data["content_plan_choices"], plans)
        self.assertIn("1. Анна — Кофейня", message.answers[-1][0])
        self.assertNotIn("День 1", message.answers[-1][0])
        keyboard = message.answers[-1][1]["reply_markup"]
        self.assertEqual(
            [[button.text for button in row] for row in keyboard.keyboard],
            [["1", "2"], [content_plan.BACK_BUTTON]],
        )

    async def test_delete_number_shows_full_plan_and_waits_for_confirmation(self):
        plans = [make_stored_plan("Анна", "Кофейня")]
        message = FakeMessage("1")
        state = FakeState(
            data={"content_plan_choices": plans},
            state=content_plan.DeleteContentPlan.waiting_for_number,
        )

        with patch(
            "handlers.content_plan.read_content_plans",
            return_value=plans,
        ):
            await content_plan.delete_content_plan(message, state)

        self.assertEqual(
            state.state,
            content_plan.DeleteContentPlan.waiting_for_confirmation,
        )
        self.assertIn(plans[0], message.answers[-1][0])
        keyboard_texts = [
            button.text
            for row in message.answers[-1][1]["reply_markup"].keyboard
            for button in row
        ]
        self.assertEqual(
            keyboard_texts,
            [
                content_plan.CONFIRM_DELETE_BUTTON,
                content_plan.CANCEL_DELETE_BUTTON,
                content_plan.BACK_BUTTON,
            ],
        )

    async def test_confirm_delete_removes_only_selected_plan(self):
        plans = [
            make_stored_plan("Анна", "Кофейня"),
            make_stored_plan("Иван", "Магазин"),
        ]
        message = FakeMessage(content_plan.CONFIRM_DELETE_BUTTON)
        state = FakeState(
            data={
                "content_plan_number": 2,
                "selected_content_plan": plans[1],
            },
            state=content_plan.DeleteContentPlan.waiting_for_confirmation,
        )

        with (
            patch(
                "handlers.content_plan.read_content_plans",
                return_value=list(plans),
            ),
            patch(
                "handlers.content_plan.save_content_plans"
            ) as save_content_plans,
        ):
            await content_plan.confirm_delete_content_plan(
                message,
                state,
            )

        save_content_plans.assert_called_once_with([plans[0]])
        self.assertTrue(state.cleared)
        self.assertIn("Контент-план удалён", message.answers[-1][0])

    async def test_confirm_delete_refreshes_changed_plan_instead_of_deleting(self):
        selected_plan = make_stored_plan("Анна", "Старый бриф")
        current_plans = [make_stored_plan("Анна", "Новый бриф")]
        message = FakeMessage(content_plan.CONFIRM_DELETE_BUTTON)
        state = FakeState(
            data={
                "content_plan_number": 1,
                "selected_content_plan": selected_plan,
            },
            state=content_plan.DeleteContentPlan.waiting_for_confirmation,
        )

        with (
            patch(
                "handlers.content_plan.read_content_plans",
                return_value=current_plans,
            ),
            patch(
                "handlers.content_plan.save_content_plans"
            ) as save_content_plans,
        ):
            await content_plan.confirm_delete_content_plan(
                message,
                state,
            )

        save_content_plans.assert_not_called()
        self.assertEqual(
            state.state,
            content_plan.DeleteContentPlan.waiting_for_number,
        )
        self.assertIn("Список изменился", message.answers[-1][0])

    async def test_cancel_delete_confirmation_returns_to_menu(self):
        message = FakeMessage(content_plan.CANCEL_DELETE_BUTTON)
        state = FakeState(
            state=content_plan.DeleteContentPlan.waiting_for_confirmation
        )

        await content_plan.cancel_delete_confirmation(message, state)

        self.assertTrue(state.cleared)
        self.assertIs(
            message.answers[-1][1]["reply_markup"],
            content_plan.content_plan_menu,
        )

    async def test_back_from_number_selection_returns_to_menu(self):
        handlers = (
            content_plan.cancel_delete,
            content_plan.cancel_edit_number,
        )

        for handler in handlers:
            with self.subTest(handler=handler.__name__):
                message = FakeMessage(content_plan.BACK_BUTTON)
                state = FakeState(state="active")

                await handler(message, state)

                self.assertTrue(state.cleared)
                self.assertIs(
                    message.answers[-1][1]["reply_markup"],
                    content_plan.content_plan_menu,
                )

    async def test_back_from_delete_confirmation_returns_to_selection(self):
        plans = [make_stored_plan("Анна", "Кофейня")]
        message = FakeMessage(content_plan.BACK_BUTTON)
        state = FakeState(
            data={
                "content_plan_number": 1,
                "selected_content_plan": plans[0],
            },
            state=content_plan.DeleteContentPlan.waiting_for_confirmation,
        )

        with patch(
            "handlers.content_plan.read_content_plans",
            return_value=plans,
        ):
            await content_plan.back_to_delete_number(message, state)

        self.assertEqual(
            state.state,
            content_plan.DeleteContentPlan.waiting_for_number,
        )
        self.assertIn("1. Анна — Кофейня", message.answers[-1][0])
        self.assertEqual(state.data["content_plan_choices"], plans)

    async def test_changed_plan_list_refreshes_stale_number(self):
        displayed_plans = [make_stored_plan("Анна", "Старый бриф")]
        current_plans = [make_stored_plan("Анна", "Новый бриф")]
        message = FakeMessage("1")
        state = FakeState(
            data={"content_plan_choices": displayed_plans},
            state=content_plan.EditContentPlan.waiting_for_number,
        )

        with patch(
            "handlers.content_plan.read_content_plans",
            return_value=current_plans,
        ):
            await content_plan.select_content_plan_for_edit(
                message,
                state,
            )

        self.assertEqual(
            state.state,
            content_plan.EditContentPlan.waiting_for_number,
        )
        self.assertEqual(
            state.data["content_plan_choices"],
            current_plans,
        )
        self.assertIn("Список изменился", message.answers[-1][0])

    async def test_edit_number_shows_full_plan_before_next_step(self):
        plans = [make_stored_plan("Анна", "Кофейня")]
        message = FakeMessage("1")
        state = FakeState(
            data={"content_plan_choices": plans},
            state=content_plan.EditContentPlan.waiting_for_number,
        )

        with (
            patch(
                "handlers.content_plan.read_content_plans",
                return_value=plans,
            ),
            patch(
                "handlers.content_plan.show_client_selection",
                new=AsyncMock(),
            ) as show_client_selection,
        ):
            await content_plan.select_content_plan_for_edit(
                message,
                state,
            )

        self.assertEqual(
            state.state,
            content_plan.EditContentPlan.waiting_for_client,
        )
        self.assertEqual(state.data["selected_content_plan"], plans[0])
        self.assertIn(plans[0], message.answers[-1][0])
        show_client_selection.assert_awaited_once_with(message)

    async def test_selecting_selected_idea_again_removes_it(self):
        idea = "Очень длинная идея " * 30
        message = FakeMessage(
            content_plan.create_idea_button_text(
                1,
                True,
            )
        )
        state = FakeState(
            data={"selected_ideas": [idea]},
            state=content_plan.CreateContentPlan.waiting_for_ideas,
        )

        with (
            patch(
                "handlers.content_plan.load_post_ideas",
                return_value=[idea],
            ),
            patch(
                "handlers.content_plan.show_idea_selection",
                new=AsyncMock(),
            ) as show_idea_selection,
        ):
            await content_plan.select_ideas_for_new_plan(
                message,
                state,
            )

        self.assertEqual(state.data["selected_ideas"], [])
        show_idea_selection.assert_awaited_once_with(
            message,
            state,
            [],
            show_full_list=False,
            post_ideas=[idea],
        )

    async def test_editing_plan_selects_idea_by_number(self):
        ideas = [
            "Первая идея",
            "Вторая очень длинная идея " * 30,
        ]
        message = FakeMessage("▫️ 2")
        state = FakeState(
            data={"selected_ideas": []},
            state=content_plan.EditContentPlan.waiting_for_ideas,
        )

        with (
            patch(
                "handlers.content_plan.load_post_ideas",
                return_value=ideas,
            ),
            patch(
                "handlers.content_plan.show_idea_selection",
                new=AsyncMock(),
            ) as show_idea_selection,
        ):
            await content_plan.select_ideas_for_edit(
                message,
                state,
            )

        self.assertEqual(
            state.data["selected_ideas"],
            [ideas[1]],
        )
        show_idea_selection.assert_awaited_once_with(
            message,
            state,
            [ideas[1]],
            show_full_list=False,
            post_ideas=ideas,
        )

    async def test_idea_selection_shows_full_and_selected_lists(self):
        ideas = [
            "Как выбрать кофе для дома",
            "Пять ошибок при заказе кофе",
        ]
        message = FakeMessage("")
        state = FakeState()

        with patch(
            "handlers.content_plan.load_post_ideas",
            return_value=ideas,
        ):
            await content_plan.show_idea_selection(
                message,
                state,
                [ideas[1]],
            )

        self.assertEqual(len(message.answers), 2)
        self.assertIn(
            "1. Как выбрать кофе для дома\n"
            "2. Пять ошибок при заказе кофе",
            message.answers[0][0],
        )
        self.assertIn(
            "✅ Выбрано:\n\n"
            "2. Пять ошибок при заказе кофе",
            message.answers[1][0],
        )
        keyboard_texts = [
            button.text
            for row in message.answers[1][1]["reply_markup"].keyboard
            for button in row
        ]
        self.assertEqual(keyboard_texts[:2], ["▫️ 1", "✅ 2"])

    async def test_back_to_ideas_preserves_selected_buttons(self):
        ideas = ["Первая идея", "Вторая идея"]
        message = FakeMessage(content_plan.BACK_BUTTON)
        state = FakeState(
            data={"selected_ideas": [ideas[1]]},
            state=content_plan.CreateContentPlan.waiting_for_brief,
        )

        with patch(
            "handlers.content_plan.load_post_ideas",
            return_value=ideas,
        ):
            await content_plan.back_to_create_idea_selection(
                message,
                state,
            )

        self.assertEqual(
            state.state,
            content_plan.CreateContentPlan.waiting_for_ideas,
        )
        keyboard_texts = [
            button.text
            for row in message.answers[-1][1]["reply_markup"].keyboard
            for button in row
        ]
        self.assertEqual(keyboard_texts[:2], ["▫️ 1", "✅ 2"])

    async def test_skip_ideas_stores_empty_list(self):
        message = FakeMessage(content_plan.SKIP_IDEAS_BUTTON)
        state = FakeState(
            data={"selected_ideas": ["Старая идея"]},
            state=content_plan.CreateContentPlan.waiting_for_ideas,
        )

        with (
            patch(
                "handlers.content_plan.load_post_ideas",
                return_value=["Старая идея"],
            ),
            patch(
                "handlers.content_plan.ask_for_brief",
                new=AsyncMock(),
            ) as ask_for_brief,
        ):
            await content_plan.select_ideas_for_new_plan(
                message,
                state,
            )

        self.assertEqual(state.data["selected_ideas"], [])
        self.assertEqual(
            state.state,
            content_plan.CreateContentPlan.waiting_for_brief,
        )
        ask_for_brief.assert_awaited_once_with(message)

    async def test_reply_markup_is_added_only_to_last_chunk(self):
        message = FakeMessage("")

        await content_plan.send_long_message(
            message,
            "Строка\n" * 1000,
            reply_markup=content_plan.content_plan_menu,
        )

        self.assertGreater(len(message.answers), 1)
        for _, kwargs in message.answers[:-1]:
            self.assertNotIn("reply_markup", kwargs)
        self.assertIs(
            message.answers[-1][1]["reply_markup"],
            content_plan.content_plan_menu,
        )

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


class BackButtonRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_general_back_handlers_only_match_without_state(self):
        modules = (
            post_ideas,
            write_post,
            content_plan,
        )
        active_state = content_plan.CreateContentPlan.waiting_for_brief.state

        for module in modules:
            with self.subTest(module=module.__name__):
                state_filter = get_state_filter(
                    module.router,
                    module.back,
                )

                self.assertTrue(
                    await state_filter(None, raw_state=None)
                )
                self.assertFalse(
                    await state_filter(
                        None,
                        raw_state=active_state,
                    )
                )

    async def test_special_back_handlers_win_for_active_states(self):
        scenarios = (
            (
                content_plan.back_to_create_idea_selection,
                content_plan.CreateContentPlan.waiting_for_brief,
                content_plan.CreateContentPlan.waiting_for_ideas,
            ),
            (
                content_plan.back_to_edit_idea_selection,
                content_plan.EditContentPlan.waiting_for_new_brief,
                content_plan.EditContentPlan.waiting_for_ideas,
            ),
        )
        general_filter = get_state_filter(
            content_plan.router,
            content_plan.back,
        )

        for callback, active_state, previous_state in scenarios:
            with self.subTest(callback=callback.__name__):
                special_handler = next(
                    handler
                    for handler in content_plan.router.message.handlers
                    if handler.callback is callback
                )
                special_filter = next(
                    filter_object.callback
                    for filter_object in special_handler.filters
                    if filter_object.callback is active_state
                )
                raw_state = active_state.state

                self.assertFalse(
                    await general_filter(
                        None,
                        raw_state=raw_state,
                    )
                )
                self.assertTrue(
                    special_filter(
                        None,
                        raw_state=raw_state,
                    )
                )

                message = FakeMessage(content_plan.BACK_BUTTON)
                state = FakeState(
                    data={"selected_ideas": ["Идея"]},
                    state=active_state,
                )

                with patch(
                    "handlers.content_plan.show_idea_selection",
                    new=AsyncMock(),
                ):
                    await callback(message, state)

                self.assertEqual(state.state, previous_state)


if __name__ == "__main__":
    unittest.main()
