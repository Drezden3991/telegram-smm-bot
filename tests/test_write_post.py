import json
import tempfile
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from handlers import write_post


class FakeMessage:
    def __init__(self, text=""):
        self.text = text
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs))


class FakeState:
    def __init__(self, data=None):
        self.cleared = False
        self.data = dict(data or {})
        self.state = None

    async def clear(self):
        self.cleared = True

    async def get_data(self):
        return dict(self.data)

    async def set_state(self, state):
        self.state = state


@contextmanager
def patch_post_persistence(posts):
    service_storage = getattr(
        write_post.write_post_service,
        "posts_storage",
        None,
    )
    load_posts = Mock(return_value=posts)
    save_posts = Mock()

    persistence_modules = [write_post]
    if service_storage is not None:
        persistence_modules.append(service_storage)

    with ExitStack() as patches:
        for persistence_module in persistence_modules:
            patches.enter_context(
                patch.object(
                    persistence_module,
                    "load_posts",
                    load_posts,
                )
            )
            patches.enter_context(
                patch.object(
                    persistence_module,
                    "save_posts",
                    save_posts,
                )
            )

        yield load_posts, save_posts


class WritePostStorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)

        self.posts_file = Path(
            self.temporary_directory.name
        ) / "posts.txt"

        self.file_patches = ExitStack()
        self.addCleanup(self.file_patches.close)

        if hasattr(write_post, "POSTS_FILE"):
            self.file_patches.enter_context(
                patch.object(
                    write_post,
                    "POSTS_FILE",
                    str(self.posts_file),
                )
            )

        if hasattr(write_post, "posts_storage"):
            self.file_patches.enter_context(
                patch.object(
                    write_post.posts_storage,
                    "POSTS_FILE",
                    str(self.posts_file),
                )
            )

    def test_load_posts_returns_empty_for_missing_file(self):
        self.assertEqual(write_post.load_posts(), [])

    def test_load_posts_returns_empty_for_invalid_json(self):
        self.posts_file.write_text(
            "{invalid json",
            encoding="utf-8",
        )

        self.assertEqual(write_post.load_posts(), [])

    def test_load_posts_returns_empty_for_non_list_json(self):
        self.posts_file.write_text(
            json.dumps({"id": 1}),
            encoding="utf-8",
        )

        self.assertEqual(write_post.load_posts(), [])

    def test_load_posts_returns_json_list_without_changes(self):
        posts = [
            {
                "id": 1,
                "client": "Иван Иванов",
                "client_context": {"name": "Иван"},
                "topic": "Новая тема",
                "style": "Экспертный",
                "text": "Текст поста",
            }
        ]
        self.posts_file.write_text(
            json.dumps(posts, ensure_ascii=False),
            encoding="utf-8",
        )

        self.assertEqual(write_post.load_posts(), posts)

    def test_save_posts_uses_utf8_readable_indented_json(self):
        posts = [
            {
                "id": 1,
                "topic": "Продвижение кофейни",
                "text": "Русский текст без ASCII-экранирования",
            }
        ]

        write_post.save_posts(posts)

        self.assertEqual(
            self.posts_file.read_text(encoding="utf-8"),
            json.dumps(
                posts,
                ensure_ascii=False,
                indent=4,
            ),
        )

    def test_saved_posts_can_be_loaded_back(self):
        posts = [
            {
                "id": 3,
                "client": "",
                "client_context": None,
                "topic": "Тема",
                "style": "Дружелюбный",
                "text": "Текст",
            }
        ]

        write_post.save_posts(posts)

        self.assertEqual(write_post.load_posts(), posts)


class WritePostClientAndIdeaLoadingTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)

        temporary_path = Path(self.temporary_directory.name)
        self.clients_file = temporary_path / "clients.txt"
        self.ideas_file = temporary_path / "post_ideas.txt"

        self.file_patches = ExitStack()
        self.addCleanup(self.file_patches.close)

        if hasattr(write_post, "CLIENTS_FILE"):
            self.file_patches.enter_context(
                patch.object(
                    write_post,
                    "CLIENTS_FILE",
                    str(self.clients_file),
                )
            )

        if hasattr(write_post, "clients_storage"):
            self.file_patches.enter_context(
                patch.object(
                    write_post.clients_storage,
                    "CLIENTS_FILE",
                    str(self.clients_file),
                )
            )

        if hasattr(write_post, "IDEAS_FILE"):
            self.file_patches.enter_context(
                patch.object(
                    write_post,
                    "IDEAS_FILE",
                    str(self.ideas_file),
                )
            )

        if hasattr(write_post, "post_ideas_storage"):
            self.file_patches.enter_context(
                patch.object(
                    write_post.post_ideas_storage,
                    "POST_IDEAS_FILE",
                    str(self.ideas_file),
                )
            )

    def test_create_client_from_current_six_field_format(self):
        line = (
            "Иван | Иванов | +372 5555 0000 | @ivan | "
            "ivan@example.com | Постоянный клиент"
        )

        self.assertEqual(
            write_post.create_client_from_line(line),
            {
                "name": "Иван",
                "last_name": "Иванов",
                "phone": "+372 5555 0000",
                "instagram": "@ivan",
                "email": "ivan@example.com",
                "notes": "Постоянный клиент",
            },
        )

    def test_create_client_from_legacy_five_field_format(self):
        line = (
            "Иван | +372 5555 0000 | @ivan | "
            "ivan@example.com | Постоянный клиент"
        )

        self.assertEqual(
            write_post.create_client_from_line(line),
            {
                "name": "Иван",
                "last_name": "",
                "phone": "+372 5555 0000",
                "instagram": "@ivan",
                "email": "ivan@example.com",
                "notes": "Постоянный клиент",
            },
        )

    def test_load_clients_reads_nonempty_lines(self):
        self.clients_file.write_text(
            "\n"
            "Иван | Иванов | +372 5555 0000 | @ivan | "
            "ivan@example.com | Заметка\n"
            "\n",
            encoding="utf-8",
        )

        self.assertEqual(
            write_post.load_clients(),
            [
                {
                    "name": "Иван",
                    "last_name": "Иванов",
                    "phone": "+372 5555 0000",
                    "instagram": "@ivan",
                    "email": "ivan@example.com",
                    "notes": "Заметка",
                }
            ],
        )

    def test_load_ideas_returns_stripped_nonempty_ideas(self):
        self.ideas_file.write_text(
            "  💡 Первая идея  \n\nВторая идея\n",
            encoding="utf-8",
        )

        self.assertEqual(
            write_post.load_ideas(),
            ["💡 Первая идея", "Вторая идея"],
        )

    def test_load_ideas_excludes_lines_containing_back_button(self):
        self.ideas_file.write_text(
            "💡 Обычная идея\n"
            "⬅️ Назад\n"
            "Текст до ⬅️ Назад и после\n",
            encoding="utf-8",
        )

        self.assertEqual(
            write_post.load_ideas(),
            ["💡 Обычная идея"],
        )

    def test_clean_idea_text_does_not_apply_other_normalization(self):
        self.assertEqual(
            write_post.clean_idea_text("💡 НОВАЯ ИДЕЯ"),
            "НОВАЯ ИДЕЯ",
        )
        self.assertEqual(
            write_post.clean_idea_text("💡НОВАЯ ИДЕЯ"),
            "💡НОВАЯ ИДЕЯ",
        )


class WritePostIdTests(unittest.TestCase):
    def test_get_next_post_id_starts_with_one_for_empty_list(self):
        self.assertEqual(write_post.get_next_post_id([]), 1)

    def test_get_next_post_id_uses_maximum_integer_id(self):
        posts = [
            {"id": 3},
            {"id": 10},
            {"id": 7},
        ]

        self.assertEqual(write_post.get_next_post_id(posts), 11)

    def test_get_next_post_id_ignores_missing_and_non_integer_ids(self):
        posts = [
            {},
            {"id": "20"},
            {"id": None},
            {"id": 4},
        ]

        self.assertEqual(write_post.get_next_post_id(posts), 5)


class WritePostBusinessLogicTests(unittest.TestCase):
    def test_get_client_full_name_joins_and_strips_name_parts(self):
        cases = (
            (
                {"name": "  Иван  ", "last_name": "  Иванов  "},
                "Иван Иванов",
            ),
            ({"name": "Иван", "last_name": ""}, "Иван"),
            ({"name": "", "last_name": "Иванов"}, "Иванов"),
            ({}, ""),
        )

        for client, expected in cases:
            with self.subTest(client=client):
                self.assertEqual(
                    write_post.get_client_full_name(client),
                    expected,
                )

    def test_clean_idea_text_preserves_current_prefix_rules(self):
        cases = (
            ("  Обычная тема  ", "Обычная тема"),
            ("💡 Тема с префиксом", "Тема с префиксом"),
            ("💡Без пробела", "💡Без пробела"),
        )

        for idea, expected in cases:
            with self.subTest(idea=idea):
                self.assertEqual(
                    write_post.clean_idea_text(idea),
                    expected,
                )

    def test_get_selected_item_requires_exact_numbered_text(self):
        items = ["Первая тема", "Вторая тема"]

        self.assertEqual(
            write_post.get_selected_item(
                "2. Вторая тема",
                items,
            ),
            1,
        )
        self.assertIsNone(
            write_post.get_selected_item(
                "Вторая тема",
                items,
            )
        )
        self.assertIsNone(
            write_post.get_selected_item(
                "1. Вторая тема",
                items,
            )
        )

    def test_create_post_text_preserves_all_style_variants(self):
        client_name = "Кофейня"
        topic = "Как выбрать кофе"
        expected_by_style = {
            "Экспертный": (
                "📝 Пост для: Кофейня\n\n"
                "Тема: Как выбрать кофе\n\n"
                "Сегодня важно говорить не просто о продукте, "
                "а о пользе, которую он даёт клиенту.\n\n"
                "Как выбрать кофе — это тема, которая помогает показать "
                "экспертность, раскрыть ценность услуги и объяснить "
                "аудитории, почему ей стоит обратить внимание именно сейчас.\n\n"
                "Хороший SMM начинается не с красивой картинки, "
                "а с понимания боли клиента и сильного сообщения."
            ),
            "Продающий": (
                "📝 Пост для: Кофейня\n\n"
                "Тема: Как выбрать кофе\n\n"
                "Если вы давно думали об этом, сейчас хороший момент начать.\n\n"
                "Как выбрать кофе помогает решить конкретную задачу клиента "
                "и сделать первый шаг к результату.\n\n"
                "Напишите нам, если хотите узнать больше "
                "или подобрать решение под вашу ситуацию."
            ),
            "Дружелюбный": (
                "📝 Пост для: Кофейня\n\n"
                "Тема: Как выбрать кофе\n\n"
                "Давайте поговорим о теме: Как выбрать кофе.\n\n"
                "Это может казаться простой вещью, но именно из таких деталей "
                "часто складывается доверие, интерес и желание узнать больше.\n\n"
                "А как вы относитесь к этой теме?"
            ),
            "Информационный": (
                "📝 Пост для: Кофейня\n\n"
                "Тема: Как выбрать кофе\n\n"
                "Как выбрать кофе — важная тема для продвижения "
                "и общения с аудиторией.\n\n"
                "Она помогает рассказать о продукте, показать пользу "
                "и объяснить, почему это может быть актуально для клиента.\n\n"
                "Регулярный контент помогает бренду оставаться "
                "заметным и понятным для своей аудитории."
            ),
        }

        for style, expected in expected_by_style.items():
            with self.subTest(style=style):
                self.assertEqual(
                    write_post.create_post_text(
                        client_name,
                        topic,
                        style,
                    ),
                    expected,
                )


class WritePostHandlerBusinessTests(unittest.IsolatedAsyncioTestCase):
    async def assert_search_finds_post(self, query, matching_field):
        posts = [
            {
                "id": 1,
                "client": "Кофейня Север",
                "topic": "Выбор зерна",
                "style": "Экспертный",
                "text": "Разбираем особенности обжарки",
            },
            {
                "id": 2,
                "client": "Другой клиент",
                "topic": "Другая тема",
                "style": "Дружелюбный",
                "text": "Другой текст",
            },
        ]
        message = FakeMessage(query)
        state = FakeState()

        with patch.object(
            write_post,
            "load_posts",
            return_value=posts,
        ):
            await write_post.get_search_result(message, state)

        self.assertTrue(state.cleared)
        self.assertEqual(
            message.answers[0][0],
            "🔎 Найдено постов: 1",
        )
        self.assertIn("ID: 1", message.answers[1][0])
        self.assertIn(matching_field, message.answers[1][0])

    async def test_search_is_case_insensitive_for_client(self):
        await self.assert_search_finds_post(
            "  КОФЕЙНЯ СЕВЕР  ",
            "Кофейня Север",
        )

    async def test_search_is_case_insensitive_for_topic(self):
        await self.assert_search_finds_post(
            "  ВЫБОР ЗЕРНА  ",
            "Выбор зерна",
        )

    async def test_search_is_case_insensitive_for_style(self):
        await self.assert_search_finds_post(
            "  ЭКСПЕРТНЫЙ  ",
            "Экспертный",
        )

    async def test_search_is_case_insensitive_for_text(self):
        await self.assert_search_finds_post(
            "  ОСОБЕННОСТИ ОБЖАРКИ  ",
            "Разбираем особенности обжарки",
        )

    async def test_post_history_uses_only_last_ten_posts(self):
        posts = [
            {
                "id": post_id,
                "client": "",
                "topic": f"Тема {post_id}",
                "style": "Информационный",
            }
            for post_id in range(1, 13)
        ]
        message = FakeMessage()

        with patch.object(
            write_post,
            "load_posts",
            return_value=posts,
        ):
            await write_post.post_history(message)

        result = message.answers[-1][0]
        shown_ids = [
            int(line.removeprefix("ID: "))
            for line in result.splitlines()
            if line.startswith("ID: ")
        ]

        self.assertEqual(shown_ids, list(range(3, 13)))

    async def test_delete_preparation_saves_posts_without_selected_id(self):
        posts = [
            {"id": 1, "text": "Первый"},
            {"id": 2, "text": "Второй"},
            {"id": 3, "text": "Третий"},
        ]
        message = FakeMessage("2")
        state = FakeState()

        with patch_post_persistence(posts) as (_, save_posts):
            await write_post.get_delete_id(message, state)

        save_posts.assert_called_once_with(
            [
                {"id": 1, "text": "Первый"},
                {"id": 3, "text": "Третий"},
            ]
        )
        self.assertTrue(state.cleared)
        self.assertEqual(
            message.answers[-1][0],
            "✅ Пост удалён.",
        )

    async def test_delete_preparation_rejects_unknown_id(self):
        posts = [
            {"id": 1, "text": "Первый"},
            {"id": 2, "text": "Второй"},
        ]
        message = FakeMessage("99")
        state = FakeState()

        with patch_post_persistence(posts) as (_, save_posts):
            await write_post.get_delete_id(message, state)

        save_posts.assert_not_called()
        self.assertFalse(state.cleared)
        self.assertEqual(
            message.answers[-1][0],
            "Пост с таким ID не найден. "
            "Попробуй ещё раз или нажми «Назад»:",
        )

    async def test_delete_rejects_non_numeric_id_without_saving(self):
        message = FakeMessage("не число")
        state = FakeState()

        with patch_post_persistence([]) as (load_posts, save_posts):
            await write_post.get_delete_id(message, state)

        load_posts.assert_not_called()
        save_posts.assert_not_called()
        self.assertFalse(state.cleared)
        self.assertEqual(
            message.answers[-1][0],
            "ID должен быть числом. Попробуй ещё раз:",
        )


class WritePostCreateHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_post_with_client_saves_exact_post_structure(self):
        client_context = {
            "name": "Иван",
            "last_name": "Иванов",
            "phone": "+372 5555 0000",
            "instagram": "@ivan",
            "email": "ivan@example.com",
            "notes": "Постоянный клиент",
        }
        existing_posts = [
            {
                "id": 7,
                "client": "Старый клиент",
                "client_context": None,
                "topic": "Старая тема",
                "style": "Информационный",
                "text": "Старый текст",
            },
            {
                "id": "100",
                "client": "",
                "client_context": None,
                "topic": "Другая тема",
                "style": "Дружелюбный",
                "text": "Другой текст",
            },
        ]
        original_existing_posts = list(existing_posts)
        state = FakeState(
            data={
                "client": "Иван Иванов",
                "client_context": client_context,
                "topic": "Как выбрать кофе",
            }
        )
        message = FakeMessage("Экспертный")

        with patch_post_persistence(
            existing_posts
        ) as (_, save_posts):
            await write_post.create_post(message, state)

        save_posts.assert_called_once()
        saved_posts = save_posts.call_args.args[0]
        created_post = saved_posts[-1]

        self.assertEqual(
            saved_posts[:-1],
            original_existing_posts,
        )
        self.assertEqual(
            set(created_post),
            {
                "id",
                "client",
                "client_context",
                "topic",
                "style",
                "text",
            },
        )
        self.assertEqual(created_post["id"], 8)
        self.assertEqual(created_post["client"], "Иван Иванов")
        self.assertIs(
            created_post["client_context"],
            client_context,
        )
        self.assertEqual(
            created_post["topic"],
            "Как выбрать кофе",
        )
        self.assertEqual(created_post["style"], "Экспертный")
        self.assertEqual(
            created_post["text"],
            write_post.create_post_text(
                "Иван Иванов",
                "Как выбрать кофе",
                "Экспертный",
            ),
        )
        self.assertTrue(state.cleared)

    async def test_create_post_without_client_preserves_empty_context(self):
        state = FakeState(
            data={
                "client": "",
                "client_context": None,
                "topic": "Тема без клиента",
            }
        )
        message = FakeMessage("Информационный")

        with patch_post_persistence([]) as (_, save_posts):
            await write_post.create_post(message, state)

        save_posts.assert_called_once()
        created_post = save_posts.call_args.args[0][-1]

        self.assertEqual(created_post["id"], 1)
        self.assertEqual(created_post["client"], "")
        self.assertIsNone(created_post["client_context"])
        self.assertEqual(
            created_post["topic"],
            "Тема без клиента",
        )
        self.assertEqual(
            created_post["style"],
            "Информационный",
        )
        self.assertTrue(state.cleared)

    async def test_create_post_without_topic_does_not_save(self):
        state = FakeState(
            data={
                "client": "Иван Иванов",
                "client_context": {"name": "Иван"},
            }
        )
        message = FakeMessage("Экспертный")

        with (
            patch_post_persistence([]) as (
                load_posts,
                save_posts,
            ),
            patch.object(
                write_post,
                "show_topic_selection",
                new=AsyncMock(),
            ) as show_topic_selection,
        ):
            await write_post.create_post(message, state)

        load_posts.assert_not_called()
        save_posts.assert_not_called()
        self.assertFalse(state.cleared)
        self.assertIs(
            state.state,
            write_post.WritePost.waiting_for_topic_choice,
        )
        show_topic_selection.assert_awaited_once_with(message)

    async def test_create_post_with_invalid_style_does_not_save(self):
        state = FakeState(
            data={
                "client": "",
                "client_context": None,
                "topic": "Тема",
            }
        )
        message = FakeMessage("Неизвестный стиль")

        with patch_post_persistence([]) as (
            load_posts,
            save_posts,
        ):
            await write_post.create_post(message, state)

        load_posts.assert_not_called()
        save_posts.assert_not_called()
        self.assertFalse(state.cleared)
        self.assertEqual(
            message.answers[-1][0],
            "Пожалуйста, выбери стиль кнопкой ниже:",
        )


if __name__ == "__main__":
    unittest.main()
