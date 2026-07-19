"""
Версия: v0.2

Описание:
Вторая версия раздела "Написать пост".

Что нового относительно v0.1:
- Пользователь может нажать «📝 Новый пост».
- Бот спрашивает тему поста.
- Бот создаёт простой текст поста по введённой теме.

Что умеет:
- Открывать раздел «Написать пост».
- Показывать меню раздела.
- Принимать тему поста от пользователя.
- Создавать простой шаблон поста.
- Возвращаться в главное меню.

Что НЕ умеет:
- Сохранять посты.
- Показывать историю постов.
- Выбирать клиента для поста.
- Генерировать посты с помощью ChatGPT.

Эта версия сохранена для будущего разбора.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from handlers.start import main_menu


router = Router()


class CreatePost(StatesGroup):
    waiting_for_topic = State()


write_post_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📝 Новый пост")],
        [KeyboardButton(text="📋 История постов")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True,
)


@router.message(F.text == "✍️ Написать пост")
async def open_write_post_menu(message: Message):
    await message.answer(
        "✍️ Раздел «Написать пост»\n\nВыбери действие:",
        reply_markup=write_post_menu
    )


@router.message(F.text == "📝 Новый пост")
async def new_post(message: Message, state: FSMContext):
    await state.set_state(CreatePost.waiting_for_topic)

    await message.answer(
        "Напиши тему поста:"
    )


@router.message(CreatePost.waiting_for_topic)
async def create_post(message: Message, state: FSMContext):
    topic = message.text

    post_text = (
        f"📝 Пост на тему: {topic}\n\n"
        f"Сегодня хочу поговорить о теме: {topic}.\n\n"
        f"Это важная тема, потому что она помогает лучше понять потребности клиентов "
        f"и показать экспертность в своей сфере.\n\n"
        f"А что вы думаете об этом?"
    )

    await state.clear()

    await message.answer(
        post_text,
        reply_markup=write_post_menu
    )


@router.message(F.text == "📋 История постов")
async def post_history(message: Message):
    await message.answer(
        "История постов пока пуста."
    )


@router.message(F.text == "⬅️ Назад")
async def back(message: Message):
    await message.answer(
        "Главное меню:",
        reply_markup=main_menu
    )