"""
Версия: v0.11

Описание:
Одиннадцатая версия раздела "Клиенты".

Что нового:
- Добавлено полное редактирование карточки клиента.
- Теперь можно редактировать:
  - имя;
  - телефон;
  - Instagram;
  - email;
  - заметки.
- Бот спрашивает, какое поле нужно изменить.
- После изменения данные сохраняются в clients.txt.

Что умеет:
- Открывать раздел «Клиенты».
- Показывать меню раздела.
- Добавлять клиента с контактами и заметками.
- Проверять дубликаты при добавлении клиента.
- Показывать список клиентов.
- Удалять клиента.
- Редактировать любое поле клиента.
- Искать клиента.
- Сохранять клиентов в clients.txt.
- Загружать клиентов из clients.txt.
- Возвращаться в главное меню.

Текущие ограничения:
- Клиент выбирается по имени.
- Фамилии клиента пока нет.
- Уникального ID клиента пока нет.
- Нет отдельной красивой карточки клиента.
- Данные всё ещё хранятся в txt, а не в базе данных.

Почему версия сохранена:
Эта версия сохраняется как первый вариант раздела,
в котором можно полноценно редактировать карточку клиента.
"""

from aiogram import F, Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from handlers.start import main_menu


router = Router()


clients = []
new_client = {}
client_to_edit = ""
field_to_edit = ""

waiting_for_client_name = False
waiting_for_client_phone = False
waiting_for_client_instagram = False
waiting_for_client_email = False
waiting_for_client_notes = False
waiting_for_client_delete = False
waiting_for_client_edit_name = False
waiting_for_client_edit_field = False
waiting_for_client_edit_value = False
waiting_for_client_search = False


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


edit_fields_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Имя")],
        [KeyboardButton(text="Телефон")],
        [KeyboardButton(text="Instagram")],
        [KeyboardButton(text="Email")],
        [KeyboardButton(text="Заметки")],
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
                    clients.append(create_client_from_line(line))
    except FileNotFoundError:
        pass


def save_clients():
    with open("clients.txt", "w", encoding="utf-8") as file:
        for client in clients:
            file.write(create_line_from_client(client) + "\n")


def create_client_from_line(line):
    parts = line.split(" | ")

    if len(parts) == 5:
        return {
            "name": parts[0],
            "phone": parts[1],
            "instagram": parts[2],
            "email": parts[3],
            "notes": parts[4],
        }

    if len(parts) == 4:
        return {
            "name": parts[0],
            "phone": parts[1],
            "instagram": parts[2],
            "email": parts[3],
            "notes": "",
        }

    return {
        "name": line,
        "phone": "",
        "instagram": "",
        "email": "",
        "notes": "",
    }


def create_line_from_client(client):
    return (
        f"{client['name']} | "
        f"{client['phone']} | "
        f"{client['instagram']} | "
        f"{client['email']} | "
        f"{client['notes']}"
    )


def find_client_by_name(client_name):
    for client in clients:
        if client["name"].lower() == client_name.lower():
            return client

    return None


def client_exists(client_name):
    client = find_client_by_name(client_name)

    if client:
        return True

    return False


def reset_waiting():
    global waiting_for_client_name
    global waiting_for_client_phone
    global waiting_for_client_instagram
    global waiting_for_client_email
    global waiting_for_client_notes
    global waiting_for_client_delete
    global waiting_for_client_edit_name
    global waiting_for_client_edit_field
    global waiting_for_client_edit_value
    global waiting_for_client_search

    waiting_for_client_name = False
    waiting_for_client_phone = False
    waiting_for_client_instagram = False
    waiting_for_client_email = False
    waiting_for_client_notes = False
    waiting_for_client_delete = False
    waiting_for_client_edit_name = False
    waiting_for_client_edit_field = False
    waiting_for_client_edit_value = False
    waiting_for_client_search = False


def format_client(client, number):
    return (
        f"{number}. {client['name']}\n"
        f"   Телефон: {client['phone']}\n"
        f"   Instagram: {client['instagram']}\n"
        f"   Email: {client['email']}\n"
        f"   Заметки: {client['notes']}\n\n"
    )


def format_clients_list(title, clients_list):
    text = title + "\n\n"

    for number, client in enumerate(clients_list, start=1):
        text += format_client(client, number)

    return text


def get_field_key(field_name):
    if field_name == "Имя":
        return "name"

    if field_name == "Телефон":
        return "phone"

    if field_name == "Instagram":
        return "instagram"

    if field_name == "Email":
        return "email"

    if field_name == "Заметки":
        return "notes"

    return ""


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
        await message.answer(
            format_clients_list("📋 Список клиентов:", clients)
        )
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
    global field_to_edit

    reset_waiting()

    new_client = {}
    client_to_edit = ""
    field_to_edit = ""

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
    global waiting_for_client_edit_field
    global waiting_for_client_edit_value
    global waiting_for_client_search
    global new_client
    global client_to_edit
    global field_to_edit

    if waiting_for_client_name:
        client_name = message.text

        if client_exists(client_name):
            waiting_for_client_name = False
            new_client = {}

            await message.answer(
                f"Клиент «{client_name}» уже существует."
            )
        else:
            new_client["name"] = client_name
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
            waiting_for_client_edit_field = True

            await message.answer(
                "Что нужно изменить?",
                reply_markup=edit_fields_menu
            )
        else:
            waiting_for_client_edit_name = False

            await message.answer(f"Клиент «{client_name}» не найден.")

    elif waiting_for_client_edit_field:
        field_name = message.text
        field_key = get_field_key(field_name)

        if field_key:
            field_to_edit = field_key
            waiting_for_client_edit_field = False
            waiting_for_client_edit_value = True

            await message.answer(f"Введите новое значение для поля «{field_name}»:")
        else:
            await message.answer("Такого поля нет. Выберите поле из меню.")

    elif waiting_for_client_edit_value:
        new_value = message.text
        client = find_client_by_name(client_to_edit)

        if client:
            if field_to_edit == "name" and client_exists(new_value):
                await message.answer(
                    f"Клиент «{new_value}» уже существует."
                )
            else:
                client[field_to_edit] = new_value
                save_clients()

                await message.answer(
                    "✅ Данные клиента обновлены.",
                    reply_markup=clients_menu
                )
        else:
            await message.answer(
                "Клиент не найден.",
                reply_markup=clients_menu
            )

        waiting_for_client_edit_value = False
        client_to_edit = ""
        field_to_edit = ""

    elif waiting_for_client_search:
        search_text = message.text.lower()
        found_clients = []

        for client in clients:
            if search_text in client["name"].lower():
                found_clients.append(client)

        waiting_for_client_search = False

        if found_clients:
            await message.answer(
                format_clients_list("🔎 Найденные клиенты:", found_clients)
            )
        else:
            await message.answer("Клиенты не найдены.")