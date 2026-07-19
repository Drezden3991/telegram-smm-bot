"""
Версия: v0.1

Описание:
Первая версия раздела "Написать пост".

Что умеет:
- Открывать раздел «Написать пост».
- Показывать меню раздела.
- Реагировать на все кнопки.
- Возвращаться в главное меню.

Что НЕ умеет:
- Создавать новый пост.
- Сохранять посты.
- Показывать историю постов.
- Генерировать посты с помощью ChatGPT.

Эта версия сохранена для будущего разбора.
"""

from aiogram import F, Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from handlers.start import main_menu


router = Router()


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
async def new_post(message: Message):
    await message.answer(
        "Функция создания нового поста пока находится в разработке."
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