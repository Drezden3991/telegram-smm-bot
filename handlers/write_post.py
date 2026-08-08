from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from handlers.start import main_menu
from services import write_post as write_post_service
from storage import clients as clients_storage
from storage import post_ideas as post_ideas_storage
from storage import posts as posts_storage


router = Router()

WITHOUT_CLIENT_BUTTON = "🚫 Без клиента"
CUSTOM_TOPIC_BUTTON = "✍️ Своя тема"
BACK_BUTTON = "⬅️ Назад"

AVAILABLE_STYLES = [
    "Экспертный",
    "Продающий",
    "Дружелюбный",
    "Информационный",
]


class WritePost(StatesGroup):
    waiting_for_client = State()
    waiting_for_topic_choice = State()
    waiting_for_custom_topic = State()
    waiting_for_style = State()
    waiting_for_search_query = State()
    waiting_for_delete_id = State()


write_post_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📝 Новый пост")],
        [KeyboardButton(text="📋 История постов")],
        [KeyboardButton(text="🔎 Поиск поста")],
        [KeyboardButton(text="🗑 Удалить пост")],
        [KeyboardButton(text=BACK_BUTTON)],
    ],
    resize_keyboard=True,
)


style_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Экспертный")],
        [KeyboardButton(text="Продающий")],
        [KeyboardButton(text="Дружелюбный")],
        [KeyboardButton(text="Информационный")],
        [KeyboardButton(text=BACK_BUTTON)],
    ],
    resize_keyboard=True,
)


def load_posts():
    return posts_storage.load_posts()


def save_posts(posts):
    posts_storage.save_posts(posts)


def get_next_post_id(posts):
    return write_post_service.get_next_post_id(posts)


def create_client_from_line(line):
    return clients_storage.create_client_from_line(line)


def load_clients():
    return clients_storage.load_clients()


def load_ideas():
    ideas = post_ideas_storage.load_post_ideas()

    return write_post_service.filter_ideas(
        ideas,
        BACK_BUTTON,
    )


def get_client_full_name(client):
    return write_post_service.get_client_full_name(client)


def clean_idea_text(idea):
    return write_post_service.clean_idea_text(idea)


def create_numbered_buttons(items):
    keyboard = []

    for number, item in enumerate(items, start=1):
        keyboard.append(
            [KeyboardButton(text=f"{number}. {item}")]
        )

    return keyboard


def create_clients_menu(clients):
    client_names = [
        get_client_full_name(client)
        for client in clients
    ]

    keyboard = create_numbered_buttons(client_names)

    keyboard.append(
        [KeyboardButton(text=WITHOUT_CLIENT_BUTTON)]
    )
    keyboard.append(
        [KeyboardButton(text=BACK_BUTTON)]
    )

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
    )


def create_ideas_menu(ideas):
    idea_names = [
        clean_idea_text(idea)
        for idea in ideas
    ]

    keyboard = create_numbered_buttons(idea_names)

    keyboard.append(
        [KeyboardButton(text=CUSTOM_TOPIC_BUTTON)]
    )
    keyboard.append(
        [KeyboardButton(text=BACK_BUTTON)]
    )

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
    )


def get_selected_item(message_text, items):
    return write_post_service.get_selected_item(
        items,
        message_text,
    )


def create_post_text(client_name, topic, style):
    return write_post_service.create_post_text(
        client_name,
        topic,
        style,
    )


async def show_client_selection(message):
    clients = load_clients()
    clients_menu = create_clients_menu(clients)

    if clients:
        await message.answer(
            "👥 Выбери клиента для поста:",
            reply_markup=clients_menu,
        )
    else:
        await message.answer(
            "Сохранённых клиентов пока нет.\n\n"
            "Можно создать пост без клиента:",
            reply_markup=clients_menu,
        )


async def show_topic_selection(message):
    ideas = load_ideas()
    ideas_menu = create_ideas_menu(ideas)

    if ideas:
        await message.answer(
            "💡 Выбери сохранённую идею "
            "или введи собственную тему:",
            reply_markup=ideas_menu,
        )
    else:
        await message.answer(
            "Сохранённых идей пока нет.\n\n"
            "Выбери «Своя тема»:",
            reply_markup=ideas_menu,
        )


@router.message(F.text == "✍️ Написать пост")
async def open_write_post_menu(message: Message):
    await message.answer(
        "✍️ Раздел «Написать пост»\n\n"
        "Выбери действие:",
        reply_markup=write_post_menu,
    )


@router.message(F.text == "📝 Новый пост")
async def new_post(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(WritePost.waiting_for_client)

    await show_client_selection(message)


@router.message(
    WritePost.waiting_for_client,
    F.text == BACK_BUTTON,
)
async def cancel_client_choice(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    await message.answer(
        "✍️ Раздел «Написать пост»\n\n"
        "Выбери действие:",
        reply_markup=write_post_menu,
    )


@router.message(WritePost.waiting_for_client)
async def get_client(
    message: Message,
    state: FSMContext,
):
    selected_text = message.text.strip()
    clients = load_clients()

    if selected_text == WITHOUT_CLIENT_BUTTON:
        await state.update_data(
            client="",
            client_context=None,
        )

    else:
        client_names = [
            get_client_full_name(client)
            for client in clients
        ]

        selected_index = get_selected_item(
            selected_text,
            client_names,
        )

        if selected_index is None:
            await message.answer(
                "Пожалуйста, выбери клиента кнопкой ниже.",
                reply_markup=create_clients_menu(clients),
            )
            return

        selected_client = clients[selected_index]
        client_name = get_client_full_name(selected_client)

        await state.update_data(
            client=client_name,
            client_context=selected_client,
        )

    await state.set_state(
        WritePost.waiting_for_topic_choice
    )

    await show_topic_selection(message)


@router.message(
    WritePost.waiting_for_topic_choice,
    F.text == BACK_BUTTON,
)
async def back_from_topic_choice(
    message: Message,
    state: FSMContext,
):
    await state.set_state(WritePost.waiting_for_client)

    await show_client_selection(message)


@router.message(WritePost.waiting_for_topic_choice)
async def get_topic_choice(
    message: Message,
    state: FSMContext,
):
    selected_text = message.text.strip()
    ideas = load_ideas()

    if selected_text == CUSTOM_TOPIC_BUTTON:
        await state.set_state(
            WritePost.waiting_for_custom_topic
        )

        await message.answer(
            "Напиши собственную тему поста:",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text=BACK_BUTTON)]
                ],
                resize_keyboard=True,
            ),
        )
        return

    clean_ideas = [
        clean_idea_text(idea)
        for idea in ideas
    ]

    selected_index = get_selected_item(
        selected_text,
        clean_ideas,
    )

    if selected_index is None:
        await message.answer(
            "Пожалуйста, выбери идею кнопкой "
            "или нажми «Своя тема».",
            reply_markup=create_ideas_menu(ideas),
        )
        return

    topic = clean_ideas[selected_index]

    await state.update_data(topic=topic)
    await state.set_state(WritePost.waiting_for_style)

    await message.answer(
        "Выбери стиль поста:",
        reply_markup=style_menu,
    )


@router.message(
    WritePost.waiting_for_custom_topic,
    F.text == BACK_BUTTON,
)
async def back_from_custom_topic(
    message: Message,
    state: FSMContext,
):
    await state.set_state(
        WritePost.waiting_for_topic_choice
    )

    await show_topic_selection(message)


@router.message(WritePost.waiting_for_custom_topic)
async def get_custom_topic(
    message: Message,
    state: FSMContext,
):
    topic = message.text.strip()

    if not topic:
        await message.answer(
            "Тема не может быть пустой. "
            "Напиши тему поста:"
        )
        return

    await state.update_data(topic=topic)
    await state.set_state(WritePost.waiting_for_style)

    await message.answer(
        "Выбери стиль поста:",
        reply_markup=style_menu,
    )


@router.message(
    WritePost.waiting_for_style,
    F.text == BACK_BUTTON,
)
async def back_from_style(
    message: Message,
    state: FSMContext,
):
    await state.set_state(
        WritePost.waiting_for_topic_choice
    )

    await show_topic_selection(message)


@router.message(WritePost.waiting_for_style)
async def create_post(
    message: Message,
    state: FSMContext,
):
    style = message.text.strip()

    if style not in AVAILABLE_STYLES:
        await message.answer(
            "Пожалуйста, выбери стиль кнопкой ниже:",
            reply_markup=style_menu,
        )
        return

    data = await state.get_data()

    client_name = data.get("client", "")
    client_context = data.get("client_context")
    topic = data.get("topic", "")

    if not topic:
        await state.set_state(
            WritePost.waiting_for_topic_choice
        )

        await message.answer(
            "Тема поста не найдена. Выбери её ещё раз."
        )
        await show_topic_selection(message)
        return

    post = write_post_service.create_and_save_post(
        client_name,
        client_context,
        topic,
        style,
    )
    post_id = post["id"]
    post_text = post["text"]

    await state.clear()

    await message.answer(
        "✅ Пост создан и сохранён.\n\n"
        f"ID поста: {post_id}\n\n"
        f"{post_text}",
        reply_markup=write_post_menu,
    )


@router.message(F.text == "📋 История постов")
async def post_history(message: Message):
    posts = load_posts()

    if not posts:
        await message.answer(
            "История постов пока пуста.",
            reply_markup=write_post_menu,
        )
        return

    last_posts = write_post_service.get_last_posts(posts)

    result = "📋 Последние посты:\n\n"

    for post in last_posts:
        client_name = post.get("client") or "Без клиента"

        result += (
            f"ID: {post.get('id', '—')}\n"
            f"Клиент: {client_name}\n"
            f"Тема: {post.get('topic', '—')}\n"
            f"Стиль: {post.get('style', '—')}\n\n"
        )

    await message.answer(
        result,
        reply_markup=write_post_menu,
    )


@router.message(F.text == "🔎 Поиск поста")
async def search_post(
    message: Message,
    state: FSMContext,
):
    await state.set_state(
        WritePost.waiting_for_search_query
    )

    await message.answer(
        "Напиши слово или фразу для поиска:"
    )


@router.message(
    WritePost.waiting_for_search_query,
    F.text == BACK_BUTTON,
)
async def cancel_search(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    await message.answer(
        "✍️ Раздел «Написать пост»\n\n"
        "Выбери действие:",
        reply_markup=write_post_menu,
    )


@router.message(WritePost.waiting_for_search_query)
async def get_search_result(
    message: Message,
    state: FSMContext,
):
    posts = load_posts()
    found_posts = write_post_service.find_posts(
        posts,
        message.text,
    )

    await state.clear()

    if not found_posts:
        await message.answer(
            "Посты не найдены.",
            reply_markup=write_post_menu,
        )
        return

    await message.answer(
        f"🔎 Найдено постов: {len(found_posts[:10])}"
    )

    for post in found_posts[:10]:
        client_name = post.get("client") or "Без клиента"

        result = (
            f"ID: {post.get('id', '—')}\n"
            f"Клиент: {client_name}\n"
            f"Тема: {post.get('topic', '—')}\n"
            f"Стиль: {post.get('style', '—')}\n\n"
            f"{post.get('text', '')}"
        )

        await message.answer(result)

    await message.answer(
        "Поиск завершён.",
        reply_markup=write_post_menu,
    )


@router.message(F.text == "🗑 Удалить пост")
async def delete_post(
    message: Message,
    state: FSMContext,
):
    posts = load_posts()

    if not posts:
        await message.answer(
            "Постов пока нет.",
            reply_markup=write_post_menu,
        )
        return

    await state.set_state(
        WritePost.waiting_for_delete_id
    )

    await message.answer(
        "Напиши ID поста, который нужно удалить:"
    )


@router.message(
    WritePost.waiting_for_delete_id,
    F.text == BACK_BUTTON,
)
async def cancel_delete(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    await message.answer(
        "✍️ Раздел «Написать пост»\n\n"
        "Выбери действие:",
        reply_markup=write_post_menu,
    )


@router.message(WritePost.waiting_for_delete_id)
async def get_delete_id(
    message: Message,
    state: FSMContext,
):
    post_id_text = message.text.strip()

    if not post_id_text.isdigit():
        await message.answer(
            "ID должен быть числом. Попробуй ещё раз:"
        )
        return

    post_id = int(post_id_text)
    post_was_deleted, _ = write_post_service.delete_post(post_id)

    if not post_was_deleted:
        await message.answer(
            "Пост с таким ID не найден. "
            "Попробуй ещё раз или нажми «Назад»:"
        )
        return

    await state.clear()

    await message.answer(
        "✅ Пост удалён.",
        reply_markup=write_post_menu,
    )


@router.message(
    StateFilter(None),
    F.text == BACK_BUTTON,
)
async def back(message: Message):
    await message.answer(
        "Главное меню:",
        reply_markup=main_menu,
    )
