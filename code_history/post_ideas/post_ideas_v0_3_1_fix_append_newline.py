"""
Версия: v0.3.1

Описание:
Исправленная версия раздела "Идея постов".

Что нового относительно v0.3:
- Исправлена ошибка, когда новая идея могла дописаться в конец последней строки файла.
- Перед сохранением новой идеи проверяется, начинается ли она со смайлика 💡.
- Если пользователь написал идею без 💡, бот добавляет смайлик автоматически.

Что умеет:
- Открывать меню раздела "Идея постов".
- Загружать идеи из файла post_ideas.txt.
- Выдавать случайную идею.
- Принимать новую идею от пользователя.
- Сохранять новую идею в файл post_ideas.txt с отдельной строки.
- Автоматически добавлять 💡 перед новой идеей.
- Возвращаться в главное меню.

Что НЕ умеет:
- Удалять идеи.
- Редактировать идеи.
- Проверять идеи на дубликаты.
- Разделять идеи по категориям.
- Генерировать идеи через ChatGPT.

Эта версия сохранена для будущего разбора.
"""

import random

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from handlers.start import main_menu


router = Router()

POST_IDEAS_FILE = "post_ideas.txt"


class AddPostIdea(StatesGroup):
    waiting_for_idea = State()


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


def format_post_idea(idea):
    idea = idea.strip()

    if not idea.startswith("💡"):
        idea = "💡 " + idea

    return idea


def save_post_idea(idea):
    idea = format_post_idea(idea)

    with open(POST_IDEAS_FILE, "a+", encoding="utf-8") as file:
        file.seek(0, 2)

        if file.tell() > 0:
            file.seek(file.tell() - 1)
            last_symbol = file.read(1)

            if last_symbol != "\n":
                file.write("\n")

        file.write(idea + "\n")


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
async def add_post_idea(message: Message, state: FSMContext):
    await state.set_state(AddPostIdea.waiting_for_idea)

    await message.answer(
        "Введите новую идею поста:"
    )


@router.message(AddPostIdea.waiting_for_idea)
async def save_new_post_idea(message: Message, state: FSMContext):
    idea = format_post_idea(message.text)

    save_post_idea(idea)

    await state.clear()

    await message.answer(
        f"✅ Идея добавлена:\n\n{idea}",
        reply_markup=post_ideas_menu
    )


@router.message(F.text == "⬅️ Назад")
async def back(message: Message):
    await message.answer(
        "Главное меню:",
        reply_markup=main_menu
    )