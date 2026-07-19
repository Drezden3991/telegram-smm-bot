"""
Версия: v0.1

Описание:
Первая версия раздела "Контент-план".

Что умеет:
- Открывать раздел «Контент-план».
- Показывать меню раздела.
- Реагировать на все кнопки.
- Возвращаться в главное меню.

Что НЕ умеет:
- Создавать контент-план.
- Сохранять контент-планы.
- Показывать список контент-планов.
- Редактировать контент-план.

Эта версия сохранена для будущего разбора.
"""

from aiogram import F, Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from handlers.start import main_menu


router = Router()


content_plan_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Создать контент-план")],
        [KeyboardButton(text="📋 Мои контент-планы")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True,
)


@router.message(F.text == "📅 Контент-план")
async def open_content_plan_menu(message: Message):
    await message.answer(
        "📅 Раздел «Контент-план»\n\nВыбери действие:",
        reply_markup=content_plan_menu
    )


@router.message(F.text == "📅 Создать контент-план")
async def create_content_plan(message: Message):
    await message.answer(
        "Функция создания контент-плана пока находится в разработке."
    )


@router.message(F.text == "📋 Мои контент-планы")
async def my_content_plans(message: Message):
    await message.answer(
        "Список контент-планов пока пуст."
    )


@router.message(F.text == "⬅️ Назад")
async def back(message: Message):
    await message.answer(
        "Главное меню:",
        reply_markup=main_menu
    )