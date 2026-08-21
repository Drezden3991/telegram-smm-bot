import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock, patch

from handlers import post_ideas
from models.post_idea import GeneratedPostIdeas
from services import post_ideas as post_ideas_service
from storage import post_ideas as post_ideas_storage


class FakeMessage:
    def __init__(self, text=""):
        self.text = text
        self.from_user = SimpleNamespace(id=None)
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


class PostIdeasFileTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)

        self.database_path = Path(
            self.temporary_directory.name
        ) / "post_ideas.db"
        self.file_patch = patch.object(
            post_ideas_storage,
            "POST_IDEAS_DATABASE",
            str(self.database_path),
        )
        self.file_patch.start()
        self.addCleanup(self.file_patch.stop)

    def test_load_post_ideas_returns_empty_for_new_database(self):
        self.assertEqual(post_ideas.load_post_ideas(), [])

    def test_load_post_ideas_returns_saved_order(self):
        post_ideas_storage.save_all_post_ideas(
            ["💡 Первая идея", "💡 Вторая идея"]
        )

        self.assertEqual(
            post_ideas.load_post_ideas(),
            ["💡 Первая идея", "💡 Вторая идея"],
        )

    def test_save_all_post_ideas_overwrites_database_records(self):
        post_ideas_storage.add_post_idea_to_file("💡 Старое содержимое")
        post_ideas_storage.save_all_post_ideas(
            ["💡 Первая идея", "💡 Вторая идея"]
        )

        self.assertEqual(
            post_ideas_storage.load_post_ideas(),
            ["💡 Первая идея", "💡 Вторая идея"],
        )

    def test_add_post_idea_compatibility_method_appends_record(self):
        post_ideas_storage.add_post_idea_to_file(
            "💡 Новая идея"
        )

        self.assertEqual(
            post_ideas_storage.load_post_ideas(),
            ["💡 Новая идея"],
        )


class PostIdeasBusinessLogicTests(unittest.TestCase):
    def test_format_post_idea_preserves_or_adds_prefix(self):
        cases = (
            ("  Новая идея  ", "💡 Новая идея"),
            ("  💡 Готовая идея  ", "💡 Готовая идея"),
            ("💡Без пробела", "💡Без пробела"),
        )

        for idea, expected in cases:
            with self.subTest(idea=idea):
                self.assertEqual(
                    post_ideas_service.format_post_idea(idea),
                    expected,
                )

    def test_normalize_post_idea_ignores_prefix_case_and_spaces(self):
        cases = (
            ("  💡 НОВАЯ ИДЕЯ  ", "новая идея"),
            ("  Новая Идея  ", "новая идея"),
            ("💡Без пробела", "без пробела"),
        )

        for idea, expected in cases:
            with self.subTest(idea=idea):
                self.assertEqual(
                    post_ideas_service.normalize_post_idea(idea),
                    expected,
                )

    def test_post_idea_exists_uses_normalized_comparison(self):
        ideas = ["💡 Первая идея", "💡 Вторая идея"]

        self.assertTrue(
            post_ideas_service.post_idea_exists(
                "  ПЕРВАЯ ИДЕЯ  ",
                ideas,
            )
        )
        self.assertTrue(
            post_ideas_service.post_idea_exists(
                "💡 вторая идея",
                ideas,
            )
        )
        self.assertFalse(
            post_ideas_service.post_idea_exists(
                "Третья идея",
                ideas,
            )
        )


class PostIdeasAiDispatcherTests(unittest.TestCase):
    def test_dispatcher_uses_selected_provider(self):
        cases = (
            (
                "openai",
                "services.post_ideas_openai.generate_openai_post_ideas",
            ),
            (
                "gemini",
                "services.post_ideas_gemini.generate_gemini_post_ideas",
            ),
            (
                "groq",
                "services.post_ideas_groq.generate_groq_post_ideas",
            ),
        )
        expected = GeneratedPostIdeas(
            ideas=["Первая", "Вторая", "Третья"]
        )

        for provider, target in cases:
            with self.subTest(provider=provider), patch(
                target,
                return_value=expected,
            ) as generate:
                result = post_ideas_service.generate_post_ideas(
                    provider,
                    "Контекст",
                    "Бриф",
                    ["💡 Существующая идея"],
                )

            self.assertIs(result, expected)
            generate.assert_called_once_with(
                "Контекст",
                "Бриф",
                ["💡 Существующая идея"],
            )

    def test_dispatcher_rejects_unknown_provider(self):
        with self.assertRaisesRegex(
            ValueError,
            "Неизвестный AI-provider",
        ):
            post_ideas_service.generate_post_ideas(
                "unknown",
                "Контекст",
                "Бриф",
                [],
            )


class PostIdeasAiHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_each_provider_is_saved_and_used_for_generation(self):
        cases = (
            (post_ideas.OPENAI_PROVIDER_BUTTON, "openai"),
            (post_ideas.GEMINI_PROVIDER_BUTTON, "gemini"),
            (post_ideas.GROQ_PROVIDER_BUTTON, "groq"),
        )

        for button_text, provider in cases:
            with self.subTest(provider=provider):
                message = FakeMessage(button_text)
                state = FakeState(
                    data={
                        "selected_client": {"name": "Иван"},
                        "ai_brief": "Идеи для кофейни",
                    },
                    state=(
                        post_ideas.GeneratePostIdeas
                        .waiting_for_provider
                    ),
                )

                with patch.object(
                    post_ideas.post_ideas_service,
                    "generate_post_idea_candidates",
                    return_value=["Первая", "Вторая", "Третья"],
                ) as generate:
                    await post_ideas.generate_ai_post_ideas(
                        message,
                        state,
                    )

                self.assertEqual(state.data["ai_provider"], provider)
                self.assertEqual(
                    state.data["ai_candidates"],
                    ["Первая", "Вторая", "Третья"],
                )
                self.assertEqual(
                    state.data["selected_ai_candidates"],
                    [],
                )
                self.assertIs(
                    state.state,
                    post_ideas.GeneratePostIdeas.waiting_for_candidates,
                )
                generate.assert_called_once_with(
                    {"name": "Иван"},
                    "Идеи для кофейни",
                    provider,
                )

    async def test_generated_candidates_are_not_saved_automatically(self):
        message = FakeMessage(post_ideas.GEMINI_PROVIDER_BUTTON)
        state = FakeState(
            data={"selected_client": None, "ai_brief": "Бриф"}
        )

        with (
            patch.object(
                post_ideas.post_ideas_service,
                "generate_post_idea_candidates",
                return_value=["Первая", "Вторая", "Третья"],
            ),
            patch.object(
                post_ideas.post_ideas_service,
                "save_selected_post_ideas",
            ) as save,
        ):
            await post_ideas.generate_ai_post_ideas(message, state)

        save.assert_not_called()

    async def test_selected_candidates_use_existing_batch_save_logic(self):
        message = FakeMessage(post_ideas.SAVE_SELECTED_IDEAS_BUTTON)
        state = FakeState(
            data={
                "ai_candidates": ["Первая", "Вторая", "Третья"],
                "selected_ai_candidates": ["Первая", "Третья"],
            }
        )

        with patch.object(
            post_ideas.post_ideas_service,
            "save_selected_post_ideas",
            return_value=(
                ["💡 Первая"],
                ["💡 Третья"],
            ),
        ) as save:
            await post_ideas.save_selected_ai_post_ideas(
                message,
                state,
            )

        save.assert_called_once_with(["Первая", "Третья"])
        self.assertTrue(state.cleared)
        self.assertIn("💡 Первая", message.answers[-1][0])
        self.assertIn("💡 Третья", message.answers[-1][0])

    async def test_provider_error_does_not_save_candidates(self):
        message = FakeMessage(post_ideas.GROQ_PROVIDER_BUTTON)
        state = FakeState(
            data={"selected_client": None, "ai_brief": "Бриф"},
            state=post_ideas.GeneratePostIdeas.waiting_for_provider,
        )
        error = post_ideas_service.PostIdeasGenerationError(
            "Groq сейчас не отвечает."
        )

        with (
            patch.object(
                post_ideas.post_ideas_service,
                "generate_post_idea_candidates",
                side_effect=error,
            ),
            patch.object(
                post_ideas.post_ideas_service,
                "save_selected_post_ideas",
            ) as save,
        ):
            await post_ideas.generate_ai_post_ideas(message, state)

        save.assert_not_called()
        self.assertFalse(state.cleared)
        self.assertIs(
            state.state,
            post_ideas.GeneratePostIdeas.waiting_for_provider,
        )
        self.assertIn(
            "Groq сейчас не отвечает.",
            message.answers[-1][0],
        )
        self.assertIsNotNone(
            message.answers[-1][1].get("reply_markup")
        )

    async def test_back_from_provider_selection_returns_to_brief(self):
        message = FakeMessage(post_ideas.BACK_BUTTON)
        state = FakeState(data={"ai_brief": "Бриф"})

        await post_ideas.back_to_ai_brief(message, state)

        self.assertIs(
            state.state,
            post_ideas.GeneratePostIdeas.waiting_for_brief,
        )
        self.assertIn("Опиши, какие идеи нужны", message.answers[-1][0])


class PostIdeasHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_random_idea_keeps_manual_flow(self):
        message = FakeMessage()

        with (
            patch.object(
                post_ideas,
                "load_post_ideas",
                return_value=["💡 Первая идея"],
            ),
            patch.object(
                post_ideas.post_ideas_service,
                "choose_random_post_idea",
                return_value="💡 Первая идея",
            ) as choose,
        ):
            await post_ideas.random_post_idea(message)

        choose.assert_called_once_with(["💡 Первая идея"])
        self.assertEqual(message.answers[-1][0], "💡 Первая идея")

    async def test_delete_prompt_stores_displayed_ideas_snapshot(self):
        ideas = ["💡 Первая идея", "💡 Вторая идея"]
        message = FakeMessage("🗑 Удалить идею")
        state = FakeState()

        with patch.object(
            post_ideas,
            "load_post_ideas",
            return_value=ideas,
        ):
            await post_ideas.delete_post_idea(
                message,
                state,
            )

        self.assertEqual(
            state.data["post_ideas_snapshot"],
            ideas,
        )
        self.assertEqual(
            state.state,
            post_ideas.DeletePostIdea.waiting_for_idea_number,
        )

    async def test_search_preserves_source_numbers_and_clears_state(self):
        message = FakeMessage("  КОФЕ  ")
        state = FakeState()
        ideas = [
            "💡 Кофе дома",
            "💡 Чай для вечера",
            "💡 Кофейные ошибки",
        ]

        with patch.object(
            post_ideas,
            "load_post_ideas",
            return_value=ideas,
        ):
            await post_ideas.show_found_post_ideas(
                message,
                state,
            )

        self.assertTrue(state.cleared)
        self.assertEqual(
            message.answers[-1][0],
            "🔍 Найденные идеи:\n\n"
            "1. 💡 Кофе дома\n"
            "3. 💡 Кофейные ошибки",
        )
        self.assertIs(
            message.answers[-1][1]["reply_markup"],
            post_ideas.post_ideas_menu,
        )

    async def test_successful_delete_uses_service_and_preserves_message(self):
        message = FakeMessage("2")
        state = FakeState(
            data={"post_ideas_snapshot": [
                "💡 Первая идея",
                "💡 Вторая идея",
                "💡 Третья идея",
            ]}
        )
        ideas = [
            "💡 Первая идея",
            "💡 Вторая идея",
            "💡 Третья идея",
        ]
        delete_post_idea = Mock(
            return_value=(
                post_ideas.post_ideas_service.IDEA_OPERATION_READY,
                "💡 Вторая идея",
                ["💡 Первая идея", "💡 Третья идея"],
            )
        )

        with patch.object(
            post_ideas.post_ideas_service,
            "delete_post_idea",
            delete_post_idea,
        ):
            await post_ideas.delete_post_idea_by_number(
                message,
                state,
            )

        delete_post_idea.assert_called_once_with(
            "2",
            ideas,
        )
        self.assertTrue(state.cleared)
        self.assertEqual(
            message.answers[-1][0],
            "🗑 Идея удалена:\n\n💡 Вторая идея",
        )
        self.assertIs(
            message.answers[-1][1]["reply_markup"],
            post_ideas.post_ideas_menu,
        )

    async def test_invalid_delete_number_does_not_save(self):
        cases = (
            ("не число", "Введите номер идеи числом."),
            ("0", "Идеи с таким номером нет."),
            ("3", "Идеи с таким номером нет."),
        )

        for message_text, expected_answer in cases:
            with self.subTest(message_text=message_text):
                message = FakeMessage(message_text)
                state = FakeState()
                deletion_status = (
                    post_ideas.post_ideas_service.IDEA_NUMBER_NOT_DIGIT
                    if message_text == "не число"
                    else post_ideas.post_ideas_service.IDEA_NUMBER_NOT_FOUND
                )
                delete_post_idea = Mock(
                    return_value=(deletion_status, None, [])
                )

                with patch.object(
                    post_ideas.post_ideas_service,
                    "delete_post_idea",
                    delete_post_idea,
                ):
                    await post_ideas.delete_post_idea_by_number(
                        message,
                        state,
                    )

                delete_post_idea.assert_called_once_with(
                    message_text,
                    None,
                )
                self.assertFalse(state.cleared)
                self.assertEqual(
                    message.answers[-1][0],
                    expected_answer,
                )


class PostIdeasCrudCharacterizationTests(
    unittest.IsolatedAsyncioTestCase
):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)

        self.database_path = Path(
            self.temporary_directory.name
        ) / "post_ideas.db"
        self.file_patch = patch.object(
            post_ideas_storage,
            "POST_IDEAS_DATABASE",
            str(self.database_path),
        )
        self.file_patch.start()
        self.addCleanup(self.file_patch.stop)

    async def test_successful_add_formats_and_appends_once(self):
        message = FakeMessage("  Новая идея  ")
        state = FakeState(
            state=post_ideas.AddPostIdea.waiting_for_idea,
        )

        with patch.object(
            post_ideas_storage,
            "add_post_idea_to_file",
            wraps=post_ideas_storage.add_post_idea_to_file,
        ) as add_post_idea:
            await post_ideas.save_new_post_idea(
                message,
                state,
            )

        add_post_idea.assert_called_once_with("💡 Новая идея")
        self.assertEqual(
            post_ideas_storage.load_post_ideas(),
            ["💡 Новая идея"],
        )
        self.assertTrue(state.cleared)
        self.assertEqual(
            message.answers[-1][0],
            "✅ Идея добавлена:\n\n💡 Новая идея",
        )

    async def test_duplicate_add_does_not_append(self):
        post_ideas_storage.save_all_post_ideas(
            ["💡 Первая идея"]
        )
        message = FakeMessage("  ПЕРВАЯ ИДЕЯ  ")
        state = FakeState(
            state=post_ideas.AddPostIdea.waiting_for_idea,
        )
        add_post_idea = Mock()

        with patch.object(
            post_ideas_storage,
            "add_post_idea_to_file",
            add_post_idea,
        ):
            await post_ideas.save_new_post_idea(
                message,
                state,
            )

        add_post_idea.assert_not_called()
        self.assertEqual(
            post_ideas_storage.load_post_ideas(),
            ["💡 Первая идея"],
        )
        self.assertTrue(state.cleared)
        self.assertEqual(
            message.answers[-1][0],
            "⚠️ Такая идея уже есть в списке.",
        )

    async def test_successful_edit_saves_only_changed_idea(self):
        original_ideas = [
            "💡 Первая идея",
            "💡 Вторая идея",
            "💡 Третья идея",
        ]
        post_ideas_storage.save_all_post_ideas(original_ideas)
        message = FakeMessage("  Обновлённая идея  ")
        state = FakeState(
            data={
                "idea_number": 2,
                "selected_idea": "💡 Вторая идея",
            },
            state=post_ideas.EditPostIdea.waiting_for_new_idea_text,
        )

        with patch.object(
            post_ideas_storage,
            "update_post_idea_by_position",
            wraps=post_ideas_storage.update_post_idea_by_position,
        ) as save_post_ideas:
            await post_ideas.save_edited_post_idea(
                message,
                state,
            )

        expected_ideas = [
            "💡 Первая идея",
            "💡 Обновлённая идея",
            "💡 Третья идея",
        ]
        save_post_ideas.assert_called_once_with(
            2,
            "💡 Обновлённая идея",
        )
        self.assertEqual(
            post_ideas_storage.load_post_ideas(),
            expected_ideas,
        )
        self.assertTrue(state.cleared)
        self.assertEqual(
            message.answers[-1][0],
            "✅ Идея обновлена:\n\n💡 Обновлённая идея",
        )

    async def test_duplicate_edit_does_not_rewrite_file(self):
        original_ideas = [
            "💡 Первая идея",
            "💡 Вторая идея",
        ]
        post_ideas_storage.save_all_post_ideas(original_ideas)
        message = FakeMessage("ПЕРВАЯ ИДЕЯ")
        state = FakeState(
            data={
                "idea_number": 2,
                "selected_idea": "💡 Вторая идея",
            },
            state=post_ideas.EditPostIdea.waiting_for_new_idea_text,
        )

        save_post_ideas = Mock()

        with patch.object(
            post_ideas_storage,
            "update_post_idea_by_position",
            save_post_ideas,
        ):
            await post_ideas.save_edited_post_idea(
                message,
                state,
            )

        save_post_ideas.assert_not_called()
        self.assertEqual(
            post_ideas_storage.load_post_ideas(),
            original_ideas,
        )
        self.assertTrue(state.cleared)
        self.assertEqual(
            message.answers[-1][0],
            "⚠️ Такая идея уже есть в списке.",
        )

    async def test_successful_delete_saves_only_remaining_ideas(self):
        original_ideas = [
            "💡 Первая идея",
            "💡 Вторая идея",
            "💡 Третья идея",
        ]
        post_ideas_storage.save_all_post_ideas(original_ideas)
        message = FakeMessage("2")
        state = FakeState(
            data={"post_ideas_snapshot": list(original_ideas)},
            state=post_ideas.DeletePostIdea.waiting_for_idea_number,
        )

        with patch.object(
            post_ideas_storage,
            "delete_post_idea_by_position",
            wraps=post_ideas_storage.delete_post_idea_by_position,
        ) as save_post_ideas:
            await post_ideas.delete_post_idea_by_number(
                message,
                state,
            )

        expected_ideas = [
            "💡 Первая идея",
            "💡 Третья идея",
        ]
        save_post_ideas.assert_called_once_with(2)
        self.assertEqual(
            post_ideas_storage.load_post_ideas(),
            expected_ideas,
        )
        self.assertTrue(state.cleared)
        self.assertEqual(
            message.answers[-1][0],
            "🗑 Идея удалена:\n\n💡 Вторая идея",
        )

    async def test_stale_delete_refreshes_snapshot_without_saving(self):
        displayed_ideas = [
            "💡 Изначальная идея",
            "💡 Вторая идея",
        ]
        current_ideas = [
            "💡 Другая идея",
            "💡 Вторая идея",
        ]
        post_ideas_storage.save_all_post_ideas(current_ideas)
        message = FakeMessage("1")
        state = FakeState(
            data={"post_ideas_snapshot": displayed_ideas},
            state=post_ideas.DeletePostIdea.waiting_for_idea_number,
        )
        save_post_ideas = Mock()

        with patch.object(
            post_ideas_storage,
            "delete_post_idea_by_position",
            save_post_ideas,
        ):
            await post_ideas.delete_post_idea_by_number(
                message,
                state,
            )

        save_post_ideas.assert_not_called()
        self.assertEqual(
            post_ideas_storage.load_post_ideas(),
            current_ideas,
        )
        self.assertFalse(state.cleared)
        self.assertEqual(
            state.data["post_ideas_snapshot"],
            current_ideas,
        )
        self.assertEqual(
            message.answers[-1][0],
            "📋 Список идей:\n\n"
            "1. 💡 Другая идея\n"
            "2. 💡 Вторая идея\n\n"
            "Введите номер идеи, которую нужно удалить:",
        )

    async def test_stale_edit_refreshes_list_without_saving(self):
        current_ideas = ["💡 Другая идея"]
        post_ideas_storage.save_all_post_ideas(current_ideas)
        message = FakeMessage("Новый текст")
        state = FakeState(
            data={
                "idea_number": 1,
                "selected_idea": "💡 Изначальная идея",
            },
            state=post_ideas.EditPostIdea.waiting_for_new_idea_text,
        )
        save_post_ideas = Mock()

        with patch.object(
            post_ideas_storage,
            "update_post_idea_by_position",
            save_post_ideas,
        ):
            await post_ideas.save_edited_post_idea(
                message,
                state,
            )

        save_post_ideas.assert_not_called()
        self.assertEqual(
            post_ideas_storage.load_post_ideas(),
            current_ideas,
        )
        self.assertFalse(state.cleared)
        self.assertEqual(
            state.state,
            post_ideas.EditPostIdea.waiting_for_idea_number,
        )
        self.assertIn(
            "Список идей изменился",
            message.answers[-1][0],
        )