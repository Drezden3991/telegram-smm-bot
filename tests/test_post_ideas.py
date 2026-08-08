import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from handlers import post_ideas
from storage import post_ideas as post_ideas_storage


class FakeMessage:
    def __init__(self, text=""):
        self.text = text
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs))


class FakeState:
    def __init__(self):
        self.cleared = False

    async def clear(self):
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

    def test_save_all_post_ideas_overwrites_and_formats_ideas(self):
        self.file_path.write_text(
            "Старое содержимое\n",
            encoding="utf-8",
        )

        post_ideas.save_all_post_ideas(
            ["Первая идея", "💡 Вторая идея"]
        )

        self.assertEqual(
            self.file_path.read_text(encoding="utf-8"),
            "💡 Первая идея\n💡 Вторая идея\n",
        )

    def test_add_post_idea_to_file_creates_formatted_line(self):
        post_ideas.add_post_idea_to_file("Новая идея")

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
                    post_ideas.format_post_idea(idea),
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
                    post_ideas.normalize_post_idea(idea),
                    expected,
                )

    def test_post_idea_exists_uses_normalized_comparison(self):
        with patch.object(
            post_ideas,
            "load_post_ideas",
            return_value=["💡 Первая идея", "💡 Вторая идея"],
        ):
            self.assertTrue(
                post_ideas.post_idea_exists("  ПЕРВАЯ ИДЕЯ  ")
            )
            self.assertTrue(
                post_ideas.post_idea_exists("💡 вторая идея")
            )
            self.assertFalse(
                post_ideas.post_idea_exists("Третья идея")
            )


class PostIdeasHandlerTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_successful_delete_saves_remaining_ideas(self):
        message = FakeMessage("2")
        state = FakeState()
        ideas = [
            "💡 Первая идея",
            "💡 Вторая идея",
            "💡 Третья идея",
        ]
        save_all_post_ideas = Mock()

        with (
            patch.object(
                post_ideas,
                "load_post_ideas",
                return_value=list(ideas),
            ),
            patch.object(
                post_ideas,
                "save_all_post_ideas",
                save_all_post_ideas,
            ),
        ):
            await post_ideas.delete_post_idea_by_number(
                message,
                state,
            )

        save_all_post_ideas.assert_called_once_with(
            ["💡 Первая идея", "💡 Третья идея"]
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
                save_all_post_ideas = Mock()

                with (
                    patch.object(
                        post_ideas,
                        "load_post_ideas",
                        return_value=[
                            "💡 Первая идея",
                            "💡 Вторая идея",
                        ],
                    ),
                    patch.object(
                        post_ideas,
                        "save_all_post_ideas",
                        save_all_post_ideas,
                    ),
                ):
                    await post_ideas.delete_post_idea_by_number(
                        message,
                        state,
                    )

                save_all_post_ideas.assert_not_called()
                self.assertFalse(state.cleared)
                self.assertEqual(
                    message.answers[-1][0],
                    expected_answer,
                )
