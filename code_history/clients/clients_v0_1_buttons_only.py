"""
Версия: v0.1

Описание:
Первая версия раздела "Клиенты".

Что умеет:
- Открывать раздел "Клиенты".
- Показывать меню клиентов.
- Реагировать на все кнопки.
- Возвращаться в главное меню.

Что НЕ умеет:
- Добавлять клиентов.
- Хранить клиентов.
- Показывать список клиентов.

Эта версия сохранена для будущего разбора.
"""

from aiogram import F, Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from handlers.start import main_menu


router = Router()


clients_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить клиента")],
        [KeyboardButton(text="📋 Список клиентов")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True,
)


@router.message(F.text == "👥 Клиенты")
async def clients(message: Message):
    await message.answer(
        "👥 Раздел «Клиенты»\n\nВыбери действие:",
        reply_markup=clients_menu
    )


@router.message(F.text == "➕ Добавить клиента")
async def add_client(message: Message):
    await message.answer(
        "Функция добавления клиента пока находится в разработке."
    )


@router.message(F.text == "📋 Список клиентов")
async def clients_list(message: Message):
    await message.answer(
        "Список клиентов пока пуст."
    )


@router.message(F.text == "⬅️ Назад")
async def back(message: Message):
    await message.answer(
        "Главное меню:",
        reply_markup=main_menu
    )