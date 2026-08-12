import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from handlers import post_ideas
from services import post_ideas as post_ideas_service
from storage import post_ideas as post_ideas_storage


class FakeMessage:
    def __init__(self, text=""):
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


class PostIdeasFileTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)

        self.file_path = Path(
            self.temporary_directory.name
        ) / "post_ideas.txt"
        self.file_patch = patch.object(
            post_ideas_storage,
            "POST_IDEAS_FILE",
            str(self.file_path),
        )
        self.file_patch.start()
        self.addCleanup(self.file_patch.stop)

    def test_load_post_ideas_returns_empty_for_missing_file(self):
        self.assertEqual(post_ideas.load_post_ideas(), [])

    def test_load_post_ideas_strips_blank_lines(self):
        self.file_path.write_text(
            "  💡 Первая идея  \n\n💡 Вторая идея\n",
            encoding="utf-8",
        )

        self.assertEqual(
            post_ideas.load_post_ideas(),
            ["💡 Первая идея", "💡 Вторая идея"],
        )

    def test_save_all_post_ideas_overwrites_file(self):
        self.file_path.write_text(
            "Старое содержимое\n",
            encoding="utf-8",
        )

        post_ideas_storage.save_all_post_ideas(
            ["💡 Первая идея", "💡 Вторая идея"]
        )

        self.assertEqual(
            self.file_path.read_text(encoding="utf-8"),
            "💡 Первая идея\n💡 Вторая идея\n",
        )

    def test_add_post_idea_to_file_appends_provided_line(self):
        post_ideas_storage.add_post_idea_to_file(
            "💡 Новая идея"
        )

        self.assertEqual(
            self.file_path.read_text(encoding="utf-8"),
            "💡 Новая идея\n",
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


class PostIdeasHandlerTests(unittest.IsolatedAsyncioTestCase):
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

        self.file_path = Path(
            self.temporary_directory.name
        ) / "post_ideas.txt"
        self.file_patch = patch.object(
            post_ideas_storage,
            "POST_IDEAS_FILE",
            str(self.file_path),
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
            "save_all_post_ideas",
            wraps=post_ideas_storage.save_all_post_ideas,
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
        save_post_ideas.assert_called_once()
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
            "save_all_post_ideas",
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
            "save_all_post_ideas",
            wraps=post_ideas_storage.save_all_post_ideas,
        ) as save_post_ideas:
            await post_ideas.delete_post_idea_by_number(
                message,
                state,
            )

        expected_ideas = [
            "💡 Первая идея",
            "💡 Третья идея",
        ]
        save_post_ideas.assert_called_once_with(expected_ideas)
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
            "save_all_post_ideas",
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
            "save_all_post_ideas",
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
