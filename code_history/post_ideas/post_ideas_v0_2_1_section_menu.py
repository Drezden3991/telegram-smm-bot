"""
Версия: v0.2.1

Описание:
Промежуточная версия раздела "Идея постов".

Что нового относительно v0.2:
- Добавлено отдельное меню раздела "Идея постов".
- Кнопка «💡 Идея постов» теперь открывает меню раздела.
- Получение случайной идеи перенесено на кнопку «💡 Получить идею».
- Добавлены кнопки «➕ Добавить идею» и «⬅️ Назад».

Что умеет:
- Открывать меню раздела "Идея постов".
- Загружать идеи из файла post_ideas.txt.
- Выдавать случайную идею из файла.
- Возвращаться в главное меню.

Что НЕ умеет:
- Добавлять новые идеи через бота.
- Удалять идеи.
- Редактировать идеи.
- Искать идеи по категориям.
- Генерировать идеи с помощью ChatGPT.

Эта версия сохранена для будущего разбора.
"""

import random

from aiogram import F, Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from handlers.start import main_menu


router = Router()

POST_IDEAS_FILE = "post_ideas.txt"


post_ideas_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💡 Получить идею")],
        [KeyboardButton(text="➕ Добавить идею")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True,
)


def load_post_ideas():
    try:
        with open(POST_IDEAS_FILE, "r", encoding="utf-8") as file:
            return [line.strip() for line in file.readlines()]
    except FileNotFoundError:
        return []


@router.message(F.text == "💡 Идея постов")
async def open_post_ideas_menu(message: Message):
    await message.answer(
        "💡 Раздел «Идея постов»\n\nВыбери действие:",
        reply_markup=post_ideas_menu
    )


@router.message(F.text == "💡 Получить идею")
async def random_post_idea(message: Message):
    post_ideas = load_post_ideas()

    if not post_ideas:
        await message.answer("Список идей пока пуст.")
        return

    idea = random.choice(post_ideas)

    await message.answer(idea)


@router.message(F.text == "➕ Добавить идею")
async def add_post_idea(message: Message):
    await message.answer(
        "Функция добавления идеи пока находится в разработке."
    )


@router.message(F.text == "⬅️ Назад")
async def back(message: Message):
    await message.answer(
        "Главное меню:",
        reply_markup=main_menu
    )