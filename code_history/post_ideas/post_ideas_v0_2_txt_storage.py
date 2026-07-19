"""
Версия: v0.2

Описание:
Вторая версия раздела "Идея постов".

Что умеет:
- Реагировать на кнопку «💡 Идея постов».
- Загружать идеи из файла post_ideas.txt.
- Выбирать случайную идею.
- Отправлять идею пользователю.

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
from aiogram.types import Message


router = Router()

POST_IDEAS_FILE = "post_ideas.txt"


def load_post_ideas():
    try:
        with open(POST_IDEAS_FILE, "r", encoding="utf-8") as file:
            return [line.strip() for line in file.readlines()]
    except FileNotFoundError:
        return []


@router.message(F.text == "💡 Идея постов")
async def random_post_idea(message: Message):
    post_ideas = load_post_ideas()

    if not post_ideas:
        await message.answer(
            "Список идей пока пуст."
        )
        return

    idea = random.choice(post_ideas)

    await message.answer(idea)