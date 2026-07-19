"""
Версия: v0.3

Описание:
Третья версия раздела "Клиенты".

Что нового:
- Клиенты больше не хранятся только в памяти.
- Добавлено сохранение клиентов в файл `clients.txt`.
- После перезапуска бота список клиентов сохраняется.

Что умеет:
- Открывать раздел "Клиенты".
- Показывать меню клиентов.
- Добавлять клиентов.
- Сохранять клиентов в `clients.txt`.
- Загружать клиентов из `clients.txt`.
- Показывать список клиентов.
- Возвращаться в главное меню.

Ограничения:
- Можно хранить только имя клиента.
- Нельзя удалить клиента.
- Нельзя изменить клиента.
- Нет поиска по клиентам.
- Используется текстовый файл вместо базы данных.

Эта версия сохранена для будущего разбора.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from handlers.start import main_menu


router = Router()

CLIENTS_FILE = "clients.txt"


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


def load_clients():
    try:
        with open(CLIENTS_FILE, "r", encoding="utf-8") as file:
            return [line.strip() for line in file.readlines()]
    except FileNotFoundError:
        return []


def save_client(client_name):
    with open(CLIENTS_FILE, "a", encoding="utf-8") as file:
        file.write(client_name + "\n")


@router.message(F.text == "👥 Клиенты")
async def clients(message: Message):
    await message.answer(
        "👥 Раздел «Клиенты»\n\nВыбери действие:",
        reply_markup=clients_menu
    )


@router.message(F.text == "➕ Добавить клиента")
async def add_client(message: Message, state: FSMContext):
    await state.set_state(AddClient.waiting_for_name)
    await message.answer("Введите имя клиента:")


@router.message(AddClient.waiting_for_name)
async def save_client_name(message: Message, state: FSMContext):
    client_name = message.text

    save_client(client_name)

    await state.clear()

    await message.answer(
        f"✅ Клиент «{client_name}» добавлен.",
        reply_markup=clients_menu
    )


@router.message(F.text == "📋 Список клиентов")
async def clients_list(message: Message):
    clients = load_clients()

    if not clients:
        await message.answer("Список клиентов пока пуст.")
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