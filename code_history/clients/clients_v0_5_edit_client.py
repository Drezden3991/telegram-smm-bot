"""
Версия: v0.5

Описание:
Пятая версия раздела "Клиенты".

Что нового:
- Добавлено редактирование клиента.
- Добавлена кнопка «✏️ Редактировать клиента».
- Бот спрашивает имя клиента, которого нужно изменить.
- Затем бот спрашивает новое имя клиента.
- После редактирования список клиентов сохраняется в clients.txt.

Что умеет:
- Открывать раздел «Клиенты».
- Показывать меню раздела.
- Добавлять клиента.
- Показывать список клиентов.
- Удалять клиента.
- Редактировать имя клиента.
- Сохранять клиентов в clients.txt.
- Загружать клиентов из clients.txt.
- Возвращаться в главное меню.

Текущие ограничения:
- Клиент редактируется только по точному имени.
- Если есть два клиента с одинаковым именем, изменится первый найденный.
- Нельзя искать клиента.
- У клиента пока нет телефона, Instagram, email и заметок.

Почему версия сохранена:
Эта версия сохраняется как первый вариант раздела,
в котором можно изменять уже добавленных клиентов.
"""

from aiogram import F, Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from handlers.start import main_menu


router = Router()


clients = []
waiting_for_client_name = False
waiting_for_client_delete = False
waiting_for_client_edit_name = False
waiting_for_new_client_name = False
client_to_edit = ""


clients_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить клиента")],
        [KeyboardButton(text="📋 Список клиентов")],
        [KeyboardButton(text="❌ Удалить клиента")],
        [KeyboardButton(text="✏️ Редактировать клиента")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True,
)


def load_clients():
    try:
        with open("clients.txt", "r", encoding="utf-8") as file:
            for line in file:
                client = line.strip()

                if client:
                    clients.append(client)
    except FileNotFoundError:
        pass


def save_clients():
    with open("clients.txt", "w", encoding="utf-8") as file:
        for client in clients:
            file.write(client + "\n")


load_clients()


@router.message(F.text == "👥 Клиенты")
async def open_clients_menu(message: Message):
    await message.answer(
        "👥 Раздел «Клиенты»\n\nВыбери действие:",
        reply_markup=clients_menu
    )


@router.message(F.text == "➕ Добавить клиента")
async def ask_client_name(message: Message):
    global waiting_for_client_name
    global waiting_for_client_delete
    global waiting_for_client_edit_name
    global waiting_for_new_client_name

    waiting_for_client_name = True
    waiting_for_client_delete = False
    waiting_for_client_edit_name = False
    waiting_for_new_client_name = False

    await message.answer("Введите имя клиента:")


@router.message(F.text == "📋 Список клиентов")
async def show_clients(message: Message):
    if clients:
        text = "📋 Список клиентов:\n\n"

        for number, client in enumerate(clients, start=1):
            text += f"{number}. {client}\n"

        await message.answer(text)
    else:
        await message.answer("Список клиентов пока пуст.")


@router.message(F.text == "❌ Удалить клиента")
async def ask_client_to_delete(message: Message):
    global waiting_for_client_name
    global waiting_for_client_delete
    global waiting_for_client_edit_name
    global waiting_for_new_client_name

    waiting_for_client_name = False
    waiting_for_client_delete = True
    waiting_for_client_edit_name = False
    waiting_for_new_client_name = False

    await message.answer("Введите имя клиента, которого нужно удалить:")


@router.message(F.text == "✏️ Редактировать клиента")
async def ask_client_to_edit(message: Message):
    global waiting_for_client_name
    global waiting_for_client_delete
    global waiting_for_client_edit_name
    global waiting_for_new_client_name

    waiting_for_client_name = False
    waiting_for_client_delete = False
    waiting_for_client_edit_name = True
    waiting_for_new_client_name = False

    await message.answer("Введите имя клиента, которого нужно изменить:")


@router.message(F.text == "⬅️ Назад")
async def back(message: Message):
    global waiting_for_client_name
    global waiting_for_client_delete
    global waiting_for_client_edit_name
    global waiting_for_new_client_name
    global client_to_edit

    waiting_for_client_name = False
    waiting_for_client_delete = False
    waiting_for_client_edit_name = False
    waiting_for_new_client_name = False
    client_to_edit = ""

    await message.answer(
        "Главное меню:",
        reply_markup=main_menu
    )


@router.message()
async def handle_client_text(message: Message):
    global waiting_for_client_name
    global waiting_for_client_delete
    global waiting_for_client_edit_name
    global waiting_for_new_client_name
    global client_to_edit

    if waiting_for_client_name:
        client_name = message.text
        clients.append(client_name)
        save_clients()

        waiting_for_client_name = False

        await message.answer(f"✅ Клиент «{client_name}» добавлен.")

    elif waiting_for_client_delete:
        client_name = message.text

        if client_name in clients:
            clients.remove(client_name)
            save_clients()

            await message.answer(f"✅ Клиент «{client_name}» удалён.")
        else:
            await message.answer(f"Клиент «{client_name}» не найден.")

        waiting_for_client_delete = False

    elif waiting_for_client_edit_name:
        client_name = message.text

        if client_name in clients:
            client_to_edit = client_name
            waiting_for_client_edit_name = False
            waiting_for_new_client_name = True

            await message.answer("Введите новое имя клиента:")
        else:
            waiting_for_client_edit_name = False

            await message.answer(f"Клиент «{client_name}» не найден.")

    elif waiting_for_new_client_name:
        new_client_name = message.text

        index = clients.index(client_to_edit)
        clients[index] = new_client_name
        save_clients()

        waiting_for_new_client_name = False
        client_to_edit = ""

        await message.answer(f"✅ Клиент изменён на «{new_client_name}».")