"""
Версия: v0.2

Описание:
Вторая версия раздела "Клиенты".

Что нового:
- Добавлена первая FSM.
- Пользователь может добавить клиента.
- Клиенты сохраняются в память программы.
- Появился просмотр списка клиентов.

Что умеет:
- Открывать раздел "Клиенты".
- Показывать меню клиентов.
- Добавлять клиентов.
- Показывать список клиентов.
- Возвращаться в главное меню.

Ограничения:
- После перезапуска бота все клиенты исчезают.
- Данные хранятся только в памяти программы.

Эта версия сохранена для будущего разбора.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from handlers.start import main_menu


router = Router()


clients = []


class AddClient(StatesGroup):
    waiting_for_name = State()


clients_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить клиента")],
        [KeyboardButton(text="📋 Список клиентов")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True,
)


@router.message(F.text == "👥 Клиенты")
async def clients_menu_open(message: Message):
    await message.answer(
        "👥 Раздел «Клиенты»\n\nВыбери действие:",
        reply_markup=clients_menu
    )


@router.message(F.text == "➕ Добавить клиента")
async def add_client(message: Message, state: FSMContext):
    await state.set_state(AddClient.waiting_for_name)

    await message.answer(
        "Введите имя клиента:"
    )


@router.message(AddClient.waiting_for_name)
async def save_client(message: Message, state: FSMContext):
    clients.append(message.text)

    await state.clear()

    await message.answer(
        f"✅ Клиент «{message.text}» добавлен."
    )


@router.message(F.text == "📋 Список клиентов")
async def clients_list(message: Message):

    if not clients:
        await message.answer(
            "Список клиентов пока пуст."
        )
        return

    text = "👥 Список клиентов:\n\n"

    for number, client in enumerate(clients, start=1):
        text += f"{number}. {client}\n"

    await message.answer(text)


@router.message(F.text == "⬅️ Назад")
async def back(message: Message):
    await message.answer(
        "Главное меню:",
        reply_markup=main_menu
    )