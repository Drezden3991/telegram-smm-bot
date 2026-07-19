import json
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from handlers.start import main_menu


router = Router()

POSTS_FILE = "posts.txt"
CLIENTS_FILE = "clients.txt"
IDEAS_FILE = "post_ideas.txt"


class WritePost(StatesGroup):
    waiting_for_client = State()
    waiting_for_topic = State()
    waiting_for_style = State()
    waiting_for_search_query = State()
    waiting_for_delete_id = State()


write_post_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📝 Новый пост")],
        [KeyboardButton(text="📋 История постов")],
        [KeyboardButton(text="🔎 Поиск поста")],
        [KeyboardButton(text="🗑 Удалить пост")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True,
)


style_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Экспертный")],
        [KeyboardButton(text="Продающий")],
        [KeyboardButton(text="Дружелюбный")],
        [KeyboardButton(text="Информационный")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True,
)


def load_posts():
    try:
        with open(POSTS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []


def save_posts(posts):
    with open(POSTS_FILE, "w", encoding="utf-8") as file:
        json.dump(posts, file, ensure_ascii=False, indent=4)


def get_next_post_id(posts):
    if not posts:
        return 1

    max_id = max(post["id"] for post in posts)
    return max_id + 1


def load_lines_from_file(filename):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return [line.strip() for line in file.readlines() if line.strip()]
    except FileNotFoundError:
        return []


def create_post_text(client, topic, style):
    client_text = client if client != "-" else "вашего проекта"

    if style == "Экспертный":
        return (
            f"📝 Пост для: {client_text}\n\n"
            f"Тема: {topic}\n\n"
            f"Сегодня важно говорить не просто о продукте, а о пользе, которую он даёт клиенту.\n\n"
            f"{topic} — это тема, которая помогает показать экспертность, раскрыть ценность услуги "
            f"и объяснить аудитории, почему ей стоит обратить внимание именно сейчас.\n\n"
            f"Хороший SMM начинается не с красивой картинки, а с понимания боли клиента и сильного сообщения."
        )

    if style == "Продающий":
        return (
            f"📝 Пост для: {client_text}\n\n"
            f"Тема: {topic}\n\n"
            f"Если вы давно думали об этом, сейчас хороший момент начать.\n\n"
            f"{topic} помогает решить конкретную задачу клиента и сделать первый шаг к результату.\n\n"
            f"Напишите нам, если хотите узнать больше или подобрать решение под вашу ситуацию."
        )

    if style == "Дружелюбный":
        return (
            f"📝 Пост для: {client_text}\n\n"
            f"Тема: {topic}\n\n"
            f"Давайте поговорим о теме: {topic}.\n\n"
            f"Это может казаться простой вещью, но именно из таких деталей часто складывается доверие, "
            f"интерес и желание узнать больше.\n\n"
            f"А как вы относитесь к этой теме?"
        )

    return (
        f"📝 Пост для: {client_text}\n\n"
        f"Тема: {topic}\n\n"
        f"{topic} — важная тема для продвижения и общения с аудиторией.\n\n"
        f"Она помогает рассказать о продукте, показать пользу и объяснить, почему это может быть актуально "
        f"для клиента.\n\n"
        f"Регулярный контент помогает бренду оставаться заметным и понятным для своей аудитории."
    )


@router.message(F.text == "✍️ Написать пост")
async def open_write_post_menu(message: Message):
    await message.answer(
        "✍️ Раздел «Написать пост»\n\nВыбери действие:",
        reply_markup=write_post_menu
    )


@router.message(F.text == "📝 Новый пост")
async def new_post(message: Message, state: FSMContext):
    clients = load_lines_from_file(CLIENTS_FILE)

    if clients:
        clients_text = "\n".join(clients[:10])
        await message.answer(
            f"👥 Доступные клиенты:\n\n{clients_text}\n\n"
            f"Напиши клиента для поста или отправь `-`, если пост без клиента:"
        )
    else:
        await message.answer(
            "Клиентов пока нет.\n\n"
            "Напиши клиента для поста или отправь `-`, если пост без клиента:"
        )

    await state.set_state(WritePost.waiting_for_client)


@router.message(WritePost.waiting_for_client, F.text == "⬅️ Назад")
async def cancel_client_choice(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "✍️ Раздел «Написать пост»\n\nВыбери действие:",
        reply_markup=write_post_menu
    )


@router.message(WritePost.waiting_for_client)
async def get_client(message: Message, state: FSMContext):
    client = message.text.strip()
    await state.update_data(client=client)

    ideas = load_lines_from_file(IDEAS_FILE)

    if ideas:
        ideas_text = "\n".join(ideas[:10])
        await message.answer(
            f"💡 Доступные идеи:\n\n{ideas_text}\n\n"
            f"Напиши тему или идею для поста:"
        )
    else:
        await message.answer(
            "Идей пока нет.\n\n"
            "Напиши тему поста:"
        )

    await state.set_state(WritePost.waiting_for_topic)


@router.message(WritePost.waiting_for_topic, F.text == "⬅️ Назад")
async def cancel_topic_choice(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "✍️ Раздел «Написать пост»\n\nВыбери действие:",
        reply_markup=write_post_menu
    )


@router.message(WritePost.waiting_for_topic)
async def get_topic(message: Message, state: FSMContext):
    topic = message.text.strip()
    await state.update_data(topic=topic)

    await message.answer(
        "Выбери стиль поста:",
        reply_markup=style_menu
    )

    await state.set_state(WritePost.waiting_for_style)


@router.message(WritePost.waiting_for_style, F.text == "⬅️ Назад")
async def cancel_style_choice(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "✍️ Раздел «Написать пост»\n\nВыбери действие:",
        reply_markup=write_post_menu
    )


@router.message(WritePost.waiting_for_style)
async def create_post(message: Message, state: FSMContext):
    style = message.text.strip()

    if style not in ["Экспертный", "Продающий", "Дружелюбный", "Информационный"]:
        await message.answer(
            "Пожалуйста, выбери стиль кнопкой ниже:",
            reply_markup=style_menu
        )
        return

    data = await state.get_data()

    client = data["client"]
    topic = data["topic"]

    posts = load_posts()
    post_id = get_next_post_id(posts)

    post_text = create_post_text(client, topic, style)

    post = {
        "id": post_id,
        "client": client,
        "topic": topic,
        "style": style,
        "text": post_text,
    }

    posts.append(post)
    save_posts(posts)

    await state.clear()

    await message.answer(
        f"✅ Пост создан и сохранён.\n\n"
        f"ID поста: {post_id}\n\n"
        f"{post_text}",
        reply_markup=write_post_menu
    )


@router.message(F.text == "📋 История постов")
async def post_history(message: Message):
    posts = load_posts()

    if not posts:
        await message.answer("История постов пока пуста.")
        return

    last_posts = posts[-10:]

    result = "📋 История постов:\n\n"

    for post in last_posts:
        result += (
            f"ID: {post['id']}\n"
            f"Клиент: {post['client']}\n"
            f"Тема: {post['topic']}\n"
            f"Стиль: {post['style']}\n\n"
        )

    await message.answer(result)


@router.message(F.text == "🔎 Поиск поста")
async def search_post(message: Message, state: FSMContext):
    await message.answer("Напиши слово или фразу для поиска:")
    await state.set_state(WritePost.waiting_for_search_query)


@router.message(WritePost.waiting_for_search_query, F.text == "⬅️ Назад")
async def cancel_search(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "✍️ Раздел «Написать пост»\n\nВыбери действие:",
        reply_markup=write_post_menu
    )


@router.message(WritePost.waiting_for_search_query)
async def get_search_result(message: Message, state: FSMContext):
    query = message.text.lower().strip()
    posts = load_posts()

    found_posts = []

    for post in posts:
        if (
            query in post["client"].lower()
            or query in post["topic"].lower()
            or query in post["style"].lower()
            or query in post["text"].lower()
        ):
            found_posts.append(post)

    await state.clear()

    if not found_posts:
        await message.answer(
            "Посты не найдены.",
            reply_markup=write_post_menu
        )
        return

    result = "🔎 Найденные посты:\n\n"

    for post in found_posts[:10]:
        result += (
            f"ID: {post['id']}\n"
            f"Клиент: {post['client']}\n"
            f"Тема: {post['topic']}\n"
            f"Стиль: {post['style']}\n\n"
            f"{post['text']}\n\n"
            f"---\n\n"
        )

    await message.answer(
        result,
        reply_markup=write_post_menu
    )


@router.message(F.text == "🗑 Удалить пост")
async def delete_post(message: Message, state: FSMContext):
    posts = load_posts()

    if not posts:
        await message.answer("Постов пока нет.")
        return

    await message.answer("Напиши ID поста, который нужно удалить:")
    await state.set_state(WritePost.waiting_for_delete_id)


@router.message(WritePost.waiting_for_delete_id, F.text == "⬅️ Назад")
async def cancel_delete(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "✍️ Раздел «Написать пост»\n\nВыбери действие:",
        reply_markup=write_post_menu
    )


@router.message(WritePost.waiting_for_delete_id)
async def get_delete_id(message: Message, state: FSMContext):
    post_id_text = message.text.strip()

    if not post_id_text.isdigit():
        await message.answer("ID должен быть числом. Попробуй ещё раз:")
        return

    post_id = int(post_id_text)
    posts = load_posts()

    updated_posts = []

    for post in posts:
        if post["id"] != post_id:
            updated_posts.append(post)

    await state.clear()

    if len(updated_posts) == len(posts):
        await message.answer(
            "Пост с таким ID не найден.",
            reply_markup=write_post_menu
        )
        return

    save_posts(updated_posts)

    await message.answer(
        "✅ Пост удалён.",
        reply_markup=write_post_menu
    )


@router.message(F.text == "⬅️ Назад")
async def back(message: Message):
    await message.answer(
        "Главное меню:",
        reply_markup=main_menu
    )