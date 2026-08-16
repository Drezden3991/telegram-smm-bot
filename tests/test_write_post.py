import tempfile
import unittest
from types import SimpleNamespace
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from handlers import write_post
from services import write_post as write_post_service
from storage import clients as clients_storage
from storage import post_ideas as post_ideas_storage
from storage import posts as posts_storage


class FakeMessage:
    def __init__(self, text=""):
        self.text = text
        self.from_user = SimpleNamespace(id=None)
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

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def set_state(self, state):
        self.state = state


@contextmanager
def patch_post_persistence(posts):
    load_posts = Mock(return_value=posts)
    add_post = Mock()
    delete_post_by_id = Mock()

    with (
        patch.object(
            posts_storage,
            "load_posts",
            load_posts,
        ),
        patch.object(
            posts_storage,
            "add_post",
            add_post,
        ),
        patch.object(
            posts_storage,
            "delete_post_by_id",
            delete_post_by_id,
        ),
    ):

        yield load_posts, add_post, delete_post_by_id


class WritePostStorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)

        self.posts_database = Path(
            self.temporary_directory.name
        ) / "posts.db"

        self.file_patches = ExitStack()
        self.addCleanup(self.file_patches.close)

        self.file_patches.enter_context(
            patch.object(
                posts_storage,
                "POSTS_DATABASE",
                str(self.posts_database),
            )
        )

    def test_load_posts_returns_empty_for_new_database(self):
        self.assertEqual(posts_storage.load_posts(), [])

    def test_load_posts_returns_saved_records_without_changes(self):
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
        posts_storage.save_posts(posts)

        self.assertEqual(posts_storage.load_posts(), posts)

    def test_save_posts_compatibility_helper_replaces_records(self):
        posts = [
            {
                "id": 1,
                "topic": "Продвижение кофейни",
                "text": "Русский текст без ASCII-экранирования",
            }
        ]

        posts_storage.add_post({"id": 9, "text": "Старый пост"})
        posts_storage.save_posts(posts)

        self.assertEqual(posts_storage.load_posts(), [
            {
                "id": 1,
                "client": "",
                "client_context": None,
                "topic": "Продвижение кофейни",
                "style": "",
                "text": "Русский текст без ASCII-экранирования",
            }
        ])

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

        posts_storage.save_posts(posts)

        self.assertEqual(posts_storage.load_posts(), posts)


class WritePostClientAndIdeaLoadingTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)

        temporary_path = Path(self.temporary_directory.name)
        self.clients_database = temporary_path / "clients.db"
        self.ideas_database = temporary_path / "post_ideas.db"

        self.file_patches = ExitStack()
        self.addCleanup(self.file_patches.close)

        if hasattr(write_post, "clients_storage"):
            self.file_patches.enter_context(
                patch.object(
                    write_post.clients_storage,
                    "CLIENTS_DATABASE",
                    str(self.clients_database),
                )
            )

        if hasattr(write_post, "post_ideas_storage"):
            self.file_patches.enter_context(
                patch.object(
                    write_post.post_ideas_storage,
                    "POST_IDEAS_DATABASE",
                    str(self.ideas_database),
                )
            )

    def test_create_client_from_current_six_field_format(self):
        line = (
            "Иван | Иванов | +372 5555 0000 | @ivan | "
            "ivan@example.com | Постоянный клиент"
        )

        self.assertEqual(
            clients_storage.create_client_from_line(line),
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
            clients_storage.create_client_from_line(line),
            {
                "name": "Иван",
                "last_name": "",
                "phone": "+372 5555 0000",
                "instagram": "@ivan",
                "email": "ivan@example.com",
                "notes": "Постоянный клиент",
            },
        )

    def test_load_clients_reads_saved_clients(self):
        clients_storage.save_clients(
            [
                clients_storage.create_client_from_line(
                    "Иван | Иванов | +372 5555 0000 | @ivan | "
                    "ivan@example.com | Заметка"
                )
            ]
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
        post_ideas_storage.save_all_post_ideas(
            ["💡 Первая идея", "Вторая идея"]
        )

        self.assertEqual(
            write_post.load_ideas(),
            ["💡 Первая идея", "Вторая идея"],
        )

    def test_load_ideas_excludes_lines_containing_back_button(self):
        post_ideas_storage.save_all_post_ideas(
            [
                "💡 Обычная идея",
                "⬅️ Назад",
                "Текст до ⬅️ Назад и после",
            ]
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
        self.assertEqual(write_post_service.get_next_post_id([]), 1)

    def test_get_next_post_id_uses_maximum_integer_id(self):
        posts = [
            {"id": 3},
            {"id": 10},
            {"id": 7},
        ]

        self.assertEqual(write_post_service.get_next_post_id(posts), 11)

    def test_get_next_post_id_ignores_missing_and_non_integer_ids(self):
        posts = [
            {},
            {"id": "20"},
            {"id": None},
            {"id": 4},
        ]

        self.assertEqual(write_post_service.get_next_post_id(posts), 5)


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
                    write_post_service.create_post_text(
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

        with patch_post_persistence(posts) as (_, _, delete_post_by_id):
            await write_post.get_delete_id(message, state)

        delete_post_by_id.assert_called_once_with(2)
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

        with patch_post_persistence(posts) as (_, _, delete_post_by_id):
            await write_post.get_delete_id(message, state)

        delete_post_by_id.assert_not_called()
        self.assertFalse(state.cleared)
        self.assertEqual(
            message.answers[-1][0],
            "Пост с таким ID не найден. "
            "Попробуй ещё раз или нажми «Назад»:",
        )

    async def test_delete_rejects_non_numeric_id_without_saving(self):
        message = FakeMessage("не число")
        state = FakeState()

        with patch_post_persistence([]) as (load_posts, add_post, delete_post_by_id):
            await write_post.get_delete_id(message, state)

        load_posts.assert_not_called()
        add_post.assert_not_called()
        delete_post_by_id.assert_not_called()
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
                "style": "Экспертный",
            }
        )
        message = FakeMessage("Экспертный")

        with patch_post_persistence(
            existing_posts
        ) as (_, add_post, _):
            await write_post.create_template_post(message, state)

        add_post.assert_called_once()
        created_post = add_post.call_args.args[0]
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
            write_post_service.create_post_text(
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
                "style": "Информационный",
            }
        )
        message = FakeMessage("Информационный")

        with patch_post_persistence([]) as (_, add_post, _):
            await write_post.create_template_post(message, state)

        add_post.assert_called_once()
        created_post = add_post.call_args.args[0]

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
                add_post,
                delete_post_by_id,
            ),
            patch.object(
                write_post,
                "show_topic_selection",
                new=AsyncMock(),
            ) as show_topic_selection,
        ):
            await write_post.create_template_post(message, state)

        load_posts.assert_not_called()
        add_post.assert_not_called()
        delete_post_by_id.assert_not_called()
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
            add_post,
            delete_post_by_id,
        ):
            await write_post.select_post_style(message, state)

        load_posts.assert_not_called()
        add_post.assert_not_called()
        delete_post_by_id.assert_not_called()
        self.assertFalse(state.cleared)
        self.assertEqual(
            message.answers[-1][0],
            "Пожалуйста, выбери стиль кнопкой ниже:",
        )


class WritePostAiDispatcherTests(unittest.TestCase):
    def test_dispatcher_uses_selected_provider(self):
        cases = (
            (
                "openai",
                "services.write_post_openai.generate_openai_post",
            ),
            (
                "gemini",
                "services.write_post_gemini.generate_gemini_post",
            ),
            (
                "groq",
                "services.write_post_groq.generate_groq_post",
            ),
        )

        for provider, target in cases:
            with self.subTest(provider=provider), patch(
                target,
                return_value="AI-текст",
            ) as generate:
                result = write_post_service.generate_ai_post(
                    provider,
                    "Контекст",
                    "Тема",
                    "Дружелюбный",
                )

            self.assertEqual(result, "AI-текст")
            generate.assert_called_once_with(
                "Контекст",
                "Тема",
                "Дружелюбный",
            )

    def test_dispatcher_rejects_unknown_provider(self):
        with self.assertRaisesRegex(
            ValueError,
            "Неизвестный AI-provider",
        ):
            write_post_service.generate_ai_post(
                "unknown",
                "Контекст",
                "Тема",
                "Дружелюбный",
            )

    def test_generation_error_does_not_load_or_save_posts(self):
        error = write_post_service.WritePostGenerationError(
            "Gemini сейчас не отвечает."
        )

        with (
            patch.object(
                write_post_service,
                "generate_ai_post",
                side_effect=error,
            ),
            patch.object(
                write_post_service.posts_storage,
                "load_posts",
            ) as load_posts,
            patch.object(
                write_post_service.posts_storage,
                "add_post",
            ) as add_post,
        ):
            with self.assertRaises(
                write_post_service.WritePostGenerationError
            ):
                write_post_service.create_and_save_ai_post(
                    "gemini",
                    "Иван Иванов",
                    {"name": "Иван", "last_name": "Иванов"},
                    "Тема",
                    "Дружелюбный",
                )

        load_posts.assert_not_called()
        add_post.assert_not_called()

    def test_successful_generation_creates_and_saves_post_once(self):
        posts = [{"id": 4, "text": "Старый пост"}]
        add_post = Mock()

        with (
            patch.object(
                write_post_service,
                "generate_ai_post",
                return_value="AI-текст",
            ) as generate,
            patch.object(
                write_post_service.posts_storage,
                "load_posts",
                return_value=posts,
            ),
            patch.object(
                write_post_service.posts_storage,
                "add_post",
                add_post,
            ),
        ):
            post = write_post_service.create_and_save_ai_post(
                "openai",
                "Иван Иванов",
                {"name": "Иван", "last_name": "Иванов"},
                "Тема",
                "Дружелюбный",
            )

        generate.assert_called_once_with(
            "openai",
            "Название или имя клиента: Иван Иванов",
            "Тема",
            "Дружелюбный",
        )
        self.assertEqual(post["id"], 5)
        self.assertEqual(post["text"], "AI-текст")
        add_post.assert_called_once_with(post)


class WritePostAiHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_style_opens_compact_method_selection(self):
        message = FakeMessage("Дружелюбный")
        state = FakeState(data={"topic": "Тема"})

        await write_post.select_post_style(message, state)

        self.assertEqual(state.data["style"], "Дружелюбный")
        self.assertIs(
            state.state,
            write_post.WritePost.waiting_for_provider,
        )
        self.assertIn(
            "Выбери способ создания поста",
            message.answers[-1][0],
        )

    async def test_each_provider_is_saved_and_used(self):
        cases = (
            (write_post.OPENAI_PROVIDER_BUTTON, "openai"),
            (write_post.GEMINI_PROVIDER_BUTTON, "gemini"),
            (write_post.GROQ_PROVIDER_BUTTON, "groq"),
        )

        for button_text, provider in cases:
            with self.subTest(provider=provider):
                message = FakeMessage(button_text)
                state = FakeState(
                    data={
                        "client": "Иван Иванов",
                        "client_context": {"name": "Иван"},
                        "topic": "Тема",
                        "style": "Дружелюбный",
                    }
                )
                post = {
                    "id": 1,
                    "client": "Иван Иванов",
                    "client_context": {"name": "Иван"},
                    "topic": "Тема",
                    "style": "Дружелюбный",
                    "text": "AI-текст",
                }

                with patch.object(
                    write_post.write_post_service,
                    "create_and_save_ai_post",
                    return_value=post,
                ) as create:
                    await write_post.create_ai_post(message, state)

                self.assertEqual(state.data["ai_provider"], provider)
                create.assert_called_once_with(
                    provider,
                    "Иван Иванов",
                    {"name": "Иван"},
                    "Тема",
                    "Дружелюбный",
                )
                self.assertTrue(state.cleared)

    async def test_provider_error_does_not_create_post(self):
        message = FakeMessage(write_post.GROQ_PROVIDER_BUTTON)
        state = FakeState(
            data={
                "topic": "Тема",
                "style": "Дружелюбный",
            }
        )
        error = write_post_service.WritePostGenerationError(
            "Groq сейчас не отвечает."
        )

        with patch.object(
            write_post.write_post_service,
            "create_and_save_ai_post",
            side_effect=error,
        ) as create:
            await write_post.create_ai_post(message, state)

        create.assert_called_once()
        self.assertTrue(state.cleared)
        self.assertIn("Groq сейчас не отвечает.", message.answers[-1][0])

    async def test_back_from_provider_selection_returns_to_style(self):
        message = FakeMessage(write_post.BACK_BUTTON)
        state = FakeState(data={"style": "Экспертный"})

        await write_post.back_from_post_method(message, state)

        self.assertIs(
            state.state,
            write_post.WritePost.waiting_for_style,
        )
        self.assertEqual(
            message.answers[-1][0], "Выбери стиль поста:")


if __name__ == "__main__":
    unittest.main()
