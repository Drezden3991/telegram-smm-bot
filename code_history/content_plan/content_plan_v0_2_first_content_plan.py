"""
Версия: v0.2

Описание:
Вторая версия раздела "Контент-план".

Что нового:
- Добавлено создание первого простого контент-плана по введённой теме.
- Кнопка «📅 Создать контент-план» теперь запускает ввод темы.

Что умеет:
- Открывать раздел «Контент-план».
- Показывать меню раздела.
- Спрашивать тему контент-плана.
- Создавать простой контент-план из 5 пунктов.
- Реагировать на кнопку «📋 Мои контент-планы».
- Возвращаться в главное меню.

Текущие ограничения:
- Контент-план создаётся по простому шаблону.
- Контент-план не сохраняется.
- Нельзя выбрать клиента.
- Нельзя выбрать количество дней.
- Нельзя редактировать созданный контент-план.

Почему версия сохранена:
Эта версия сохраняется как первый рабочий вариант создания контент-плана.
Она показывает переход от меню-заглушки к первой полезной функции раздела.
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
        "Список контент-планов пока пуст."
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

        await message.answer(
            "📅 Контент-план\n\n"
            f"Тема: {topic}\n\n"
            "1. Знакомство с темой.\n"
            "2. Главная проблема аудитории.\n"
            "3. Полезный совет по теме.\n"
            "4. Ошибка, которую часто допускают.\n"
            "5. Призыв к действию."
        )