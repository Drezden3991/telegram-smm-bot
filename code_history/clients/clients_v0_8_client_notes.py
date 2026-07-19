"""
Версия: v0.8

Описание:
Восьмая версия раздела "Клиенты".

Что нового:
- У клиента появились заметки.
- Добавление клиента теперь включает ввод заметок.
- Клиенты сохраняются в clients.txt вместе с заметками.

Что умеет:
- Открывать раздел «Клиенты».
- Показывать меню раздела.
- Добавлять клиента с контактами и заметками.
- Показывать список клиентов.
- Удалять клиента.
- Редактировать имя клиента.
- Искать клиента.
- Сохранять клиентов в clients.txt.
- Загружать клиентов из clients.txt.
- Возвращаться в главное меню.

Текущие ограничения:
- Редактировать можно только имя клиента.
- Телефон, Instagram, email и заметки пока нельзя изменить отдельно.
- Нет отдельной красивой карточки клиента.
- Данные всё ещё хранятся в txt, а не в базе данных.

Почему версия сохранена:
Эта версия сохраняется как первый вариант раздела,
в котором у клиента есть заметки.
"""

from aiogram import F, Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from handlers.start import main_menu


router = Router()


clients = []

waiting_for_client_name = False
waiting_for_client_phone = False
waiting_for_client_instagram = False
waiting_for_client_email = False
waiting_for_client_notes = False

waiting_for_client_delete = False
waiting_for_client_edit_name = False
waiting_for_new_client_name = False
waiting_for_client_search = False

new_client = {}
client_to_edit = ""


clients_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить клиента")],
        [KeyboardButton(text="📋 Список клиентов")],
        [KeyboardButton(text="❌ Удалить клиента")],
        [KeyboardButton(text="✏️ Редактировать клиента")],
        [KeyboardButton(text="🔎 Найти клиента")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True,
)


def load_clients():
    try:
        with open("clients.txt", "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()

                if line:
                    parts = line.split(" | ")

                    if len(parts) == 5:
                        client = {
                            "name": parts[0],
                            "phone": parts[1],
                            "instagram": parts[2],
                            "email": parts[3],
                            "notes": parts[4],
                        }
                    elif len(parts) == 4:
                        client = {
                            "name": parts[0],
                            "phone": parts[1],
                            "instagram": parts[2],
                            "email": parts[3],
                            "notes": "",
                        }
                    else:
                        client = {
                            "name": line,
                            "phone": "",
                            "instagram": "",
                            "email": "",
                            "notes": "",
                        }

                    clients.append(client)
    except FileNotFoundError:
        pass


def save_clients():
    with open("clients.txt", "w", encoding="utf-8") as file:
        for client in clients:
            line = (
                f"{client['name']} | "
                f"{client['phone']} | "
                f"{client['instagram']} | "
                f"{client['email']} | "
                f"{client['notes']}"
            )

            file.write(line + "\n")


def find_client_by_name(client_name):
    for client in clients:
        if client["name"] == client_name:
            return client

    return None


def reset_waiting():
    global waiting_for_client_name
    global waiting_for_client_phone
    global waiting_for_client_instagram
    global waiting_for_client_email
    global waiting_for_client_notes
    global waiting_for_client_delete
    global waiting_for_client_edit_name
    global waiting_for_new_client_name
    global waiting_for_client_search

    waiting_for_client_name = False
    waiting_for_client_phone = False
    waiting_for_client_instagram = False
    waiting_for_client_email = False
    waiting_for_client_notes = False
    waiting_for_client_delete = False
    waiting_for_client_edit_name = False
    waiting_for_new_client_name = False
    waiting_for_client_search = False


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
    global new_client

    reset_waiting()

    new_client = {}
    waiting_for_client_name = True

    await message.answer("Введите имя клиента:")


@router.message(F.text == "📋 Список клиентов")
async def show_clients(message: Message):
    if clients:
        text = "📋 Список клиентов:\n\n"

        for number, client in enumerate(clients, start=1):
            text += f"{number}. {client['name']}\n"
            text += f"   Телефон: {client['phone']}\n"
            text += f"   Instagram: {client['instagram']}\n"
            text += f"   Email: {client['email']}\n"
            text += f"   Заметки: {client['notes']}\n\n"

        await message.answer(text)
    else:
        await message.answer("Список клиентов пока пуст.")


@router.message(F.text == "❌ Удалить клиента")
async def ask_client_to_delete(message: Message):
    global waiting_for_client_delete

    reset_waiting()

    waiting_for_client_delete = True

    await message.answer("Введите имя клиента, которого нужно удалить:")


@router.message(F.text == "✏️ Редактировать клиента")
async def ask_client_to_edit(message: Message):
    global waiting_for_client_edit_name

    reset_waiting()

    waiting_for_client_edit_name = True

    await message.answer("Введите имя клиента, которого нужно изменить:")


@router.message(F.text == "🔎 Найти клиента")
async def ask_client_to_search(message: Message):
    global waiting_for_client_search

    reset_waiting()

    waiting_for_client_search = True

    await message.answer("Введите имя или часть имени клиента:")


@router.message(F.text == "⬅️ Назад")
async def back(message: Message):
    global new_client
    global client_to_edit

    reset_waiting()

    new_client = {}
    client_to_edit = ""

    await message.answer(
        "Главное меню:",
        reply_markup=main_menu
    )


@router.message()
async def handle_client_text(message: Message):
    global waiting_for_client_name
    global waiting_for_client_phone
    global waiting_for_client_instagram
    global waiting_for_client_email
    global waiting_for_client_notes
    global waiting_for_client_delete
    global waiting_for_client_edit_name
    global waiting_for_new_client_name
    global waiting_for_client_search
    global new_client
    global client_to_edit

    if waiting_for_client_name:
        new_client["name"] = message.text
        waiting_for_client_name = False
        waiting_for_client_phone = True

        await message.answer("Введите телефон клиента:")

    elif waiting_for_client_phone:
        new_client["phone"] = message.text
        waiting_for_client_phone = False
        waiting_for_client_instagram = True

        await message.answer("Введите Instagram клиента:")

    elif waiting_for_client_instagram:
        new_client["instagram"] = message.text
        waiting_for_client_instagram = False
        waiting_for_client_email = True

        await message.answer("Введите email клиента:")

    elif waiting_for_client_email:
        new_client["email"] = message.text
        waiting_for_client_email = False
        waiting_for_client_notes = True

        await message.answer("Введите заметки о клиенте:")

    elif waiting_for_client_notes:
        new_client["notes"] = message.text

        clients.append(new_client)
        save_clients()

        client_name = new_client["name"]

        new_client = {}
        waiting_for_client_notes = False

        await message.answer(f"✅ Клиент «{client_name}» добавлен.")

    elif waiting_for_client_delete:
        client_name = message.text
        client = find_client_by_name(client_name)

        if client:
            clients.remove(client)
            save_clients()

            await message.answer(f"✅ Клиент «{client_name}» удалён.")
        else:
            await message.answer(f"Клиент «{client_name}» не найден.")

        waiting_for_client_delete = False

    elif waiting_for_client_edit_name:
        client_name = message.text
        client = find_client_by_name(client_name)

        if client:
            client_to_edit = client_name
            waiting_for_client_edit_name = False
            waiting_for_new_client_name = True

            await message.answer("Введите новое имя клиента:")
        else:
            waiting_for_client_edit_name = False

            await message.answer(f"Клиент «{client_name}» не найден.")

    elif waiting_for_new_client_name:
        new_client_name = message.text
        client = find_client_by_name(client_to_edit)

        if client:
            client["name"] = new_client_name
            save_clients()

            await message.answer(f"✅ Клиент изменён на «{new_client_name}».")
        else:
            await message.answer("Клиент не найден.")

        waiting_for_new_client_name = False
        client_to_edit = ""

    elif waiting_for_client_search:
        search_text = message.text.lower()
        found_clients = []

        for client in clients:
            if search_text in client["name"].lower():
                found_clients.append(client)

        waiting_for_client_search = False

        if found_clients:
            text = "🔎 Найденные клиенты:\n\n"

            for number, client in enumerate(found_clients, start=1):
                text += f"{number}. {client['name']}\n"
                text += f"   Телефон: {client['phone']}\n"
                text += f"   Instagram: {client['instagram']}\n"
                text += f"   Email: {client['email']}\n"
                text += f"   Заметки: {client['notes']}\n\n"

            await message.answer(text)
        else:
            await message.answer("Клиенты не найдены.")