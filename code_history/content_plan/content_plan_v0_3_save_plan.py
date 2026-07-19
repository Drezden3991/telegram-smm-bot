"""
Версия: v0.3

Описание:
Третья версия раздела "Контент-план".

Что нового:
- Добавлено сохранение созданного контент-плана в файл.

Что умеет:
- Открывать раздел «Контент-план».
- Показывать меню раздела.
- Запрашивать тему контент-плана.
- Создавать простой контент-план.
- Сохранять контент-план в файл.
- Реагировать на кнопку «📋 Мои контент-планы».
- Возвращаться в главное меню.

Текущие ограничения:
- Все контент-планы сохраняются в один файл.
- Нельзя посмотреть сохранённые контент-планы.
- Нельзя удалить контент-план.
- Нельзя редактировать контент-план.
- Не используется ChatGPT для генерации плана.

Почему версия сохранена:
Эта версия сохраняется как первый вариант, в котором
контент-план не только создаётся, но и сохраняется.
"""

from aiogram import F, Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from handlers.start import main_menu


router = Router()


waiting_for_content_plan_topic = False


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
async def ask_content_plan_topic(message: Message):
    global waiting_for_content_plan_topic

    waiting_for_content_plan_topic = True

    await message.answer(
        "Введите тему для контент-плана:"
    )


@router.message(F.text == "📋 Мои контент-планы")
async def my_content_plans(message: Message):
    await message.answer(
        "Просмотр сохранённых контент-планов пока находится в разработке."
    )


@router.message(F.text == "⬅️ Назад")
async def back(message: Message):
    global waiting_for_content_plan_topic

    waiting_for_content_plan_topic = False

    await message.answer(
        "Главное меню:",
        reply_markup=main_menu
    )


@router.message()
async def create_first_content_plan(message: Message):
    global waiting_for_content_plan_topic

    if waiting_for_content_plan_topic:
        topic = message.text
        waiting_for_content_plan_topic = False

        content_plan = (
            "📅 Контент-план\n\n"
            f"Тема: {topic}\n\n"
            "1. Знакомство с темой.\n"
            "2. Главная проблема аудитории.\n"
            "3. Полезный совет по теме.\n"
            "4. Ошибка, которую часто допускают.\n"
            "5. Призыв к действию."
        )

        with open("content_plans.txt", "a", encoding="utf-8") as file:
            file.write(content_plan)
            file.write("\n")
            file.write("-" * 40)
            file.write("\n")

        await message.answer(content_plan)
        await message.answer("✅ Контент-план успешно сохранён.")