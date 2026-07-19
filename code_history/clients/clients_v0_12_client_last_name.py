"""
Версия: v0.12

Описание:
Двенадцатая версия раздела "Клиенты".

Что нового:
- У клиента появилась фамилия.
- Добавление клиента теперь включает ввод имени и фамилии.
- Проверка дубликатов теперь работает по имени и фамилии.
- Поиск клиента работает по имени и фамилии.
- Клиенты сохраняются в clients.txt вместе с фамилией.

Что умеет:
- Открывать раздел «Клиенты».
- Показывать меню раздела.
- Добавлять клиента с именем, фамилией, контактами и заметками.
- Проверять дубликаты по имени и фамилии.
- Показывать список клиентов.
- Удалять клиента.
- Редактировать любое поле клиента.
- Искать клиента.
- Сохранять клиентов в clients.txt.
- Загружать клиентов из clients.txt.
- Возвращаться в главное меню.

Текущие ограничения:
- Клиент всё ещё выбирается по имени и фамилии, а не по ID.
- Уникального ID клиента пока нет.
- Нет отдельной красивой карточки клиента.
- Данные всё ещё хранятся в txt, а не в базе данных.

Почему версия сохранена:
Эта версия сохраняется как первый вариант раздела,
в котором у клиента есть не только имя, но и фамилия.
"""

from aiogram import F, Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from handlers.start import main_menu


router = Router()


clients = []
new_client = {}
client_to_edit = {}
field_to_edit = ""

waiting_for_client_name = False
waiting_for_client_last_name = False
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
        [KeyboardButton(text="Фамилия")],
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

    if len(parts) == 6:
        return {
            "name": parts[0],
            "last_name": parts[1],
            "phone": parts[2],
            "instagram": parts[3],
            "email": parts[4],
            "notes": parts[5],
        }

    if len(parts) == 5:
        return {
            "name": parts[0],
            "last_name": "",
            "phone": parts[1],
            "instagram": parts[2],
            "email": parts[3],
            "notes": parts[4],
        }

    if len(parts) == 4:
        return {
            "name": parts[0],
            "last_name": "",
            "phone": parts[1],
            "instagram": parts[2],
            "email": parts[3],
            "notes": "",
        }

    return {
        "name": line,
        "last_name": "",
        "phone": "",
        "instagram": "",
        "email": "",
        "notes": "",
    }


def create_line_from_client(client):
    return (
        f"{client['name']} | "
        f"{client['last_name']} | "
        f"{client['phone']} | "
        f"{client['instagram']} | "
        f"{client['email']} | "
        f"{client['notes']}"
    )


def find_client_by_full_name(name, last_name):
    for client in clients:
        same_name = client["name"].lower() == name.lower()
        same_last_name = client["last_name"].lower() == last_name.lower()

        if same_name and same_last_name:
            return client

    return None


def client_exists(name, last_name):
    client = find_client_by_full_name(name, last_name)

    if client:
        return True

    return False


def reset_waiting():
    global waiting_for_client_name
    global waiting_for_client_last_name
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
    waiting_for_client_last_name = False
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
        f"{number}. {client['name']} {client['last_name']}\n"
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

    if field_name == "Фамилия":
        return "last_name"

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

    await message.answer("Введите имя и фамилию клиента через пробел:")


@router.message(F.text == "✏️ Редактировать клиента")
async def ask_client_to_edit(message: Message):
    global waiting_for_client_edit_name

    reset_waiting()

    waiting_for_client_edit_name = True

    await message.answer("Введите имя и фамилию клиента через пробел:")


@router.message(F.text == "🔎 Найти клиента")
async def ask_client_to_search(message: Message):
    global waiting_for_client_search

    reset_waiting()

    waiting_for_client_search = True

    await message.answer("Введите имя, фамилию или часть текста для поиска:")


@router.message(F.text == "⬅️ Назад")
async def back(message: Message):
    global new_client
    global client_to_edit
    global field_to_edit

    reset_waiting()

    new_client = {}
    client_to_edit = {}
    field_to_edit = ""

    await message.answer(
        "Главное меню:",
        reply_markup=main_menu
    )


@router.message()
async def handle_client_text(message: Message):
    global waiting_for_client_name
    global waiting_for_client_last_name
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
        new_client["name"] = message.text
        waiting_for_client_name = False
        waiting_for_client_last_name = True

        await message.answer("Введите фамилию клиента:")

    elif waiting_for_client_last_name:
        new_client["last_name"] = message.text

        if client_exists(new_client["name"], new_client["last_name"]):
            new_client = {}
            waiting_for_client_last_name = False

            await message.answer("Такой клиент уже существует.")
        else:
            waiting_for_client_last_name = False
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

        full_name = f"{new_client['name']} {new_client['last_name']}"

        new_client = {}
        waiting_for_client_notes = False

        await message.answer(f"✅ Клиент «{full_name}» добавлен.")

    elif waiting_for_client_delete:
        parts = message.text.split(maxsplit=1)

        if len(parts) < 2:
            await message.answer("Введите и имя, и фамилию клиента.")
        else:
            name = parts[0]
            last_name = parts[1]
            client = find_client_by_full_name(name, last_name)

            if client:
                clients.remove(client)
                save_clients()

                await message.answer(f"✅ Клиент «{name} {last_name}» удалён.")
            else:
                await message.answer(f"Клиент «{name} {last_name}» не найден.")

            waiting_for_client_delete = False

    elif waiting_for_client_edit_name:
        parts = message.text.split(maxsplit=1)

        if len(parts) < 2:
            await message.answer("Введите и имя, и фамилию клиента.")
        else:
            name = parts[0]
            last_name = parts[1]
            client = find_client_by_full_name(name, last_name)

            if client:
                client_to_edit = client
                waiting_for_client_edit_name = False
                waiting_for_client_edit_field = True

                await message.answer(
                    "Что нужно изменить?",
                    reply_markup=edit_fields_menu
                )
            else:
                waiting_for_client_edit_name = False

                await message.answer(f"Клиент «{name} {last_name}» не найден.")

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

        if client_to_edit:
            old_name = client_to_edit["name"]
            old_last_name = client_to_edit["last_name"]

            if field_to_edit == "name":
                if client_exists(new_value, old_last_name):
                    await message.answer(
                        f"Клиент «{new_value} {old_last_name}» уже существует.",
                        reply_markup=clients_menu
                    )
                else:
                    client_to_edit["name"] = new_value
                    save_clients()

                    await message.answer(
                        "✅ Данные клиента обновлены.",
                        reply_markup=clients_menu
                    )

            elif field_to_edit == "last_name":
                if client_exists(old_name, new_value):
                    await message.answer(
                        f"Клиент «{old_name} {new_value}» уже существует.",
                        reply_markup=clients_menu
                    )
                else:
                    client_to_edit["last_name"] = new_value
                    save_clients()

                    await message.answer(
                        "✅ Данные клиента обновлены.",
                        reply_markup=clients_menu
                    )

            else:
                client_to_edit[field_to_edit] = new_value
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
        client_to_edit = {}
        field_to_edit = ""

    elif waiting_for_client_search:
        search_text = message.text.lower()
        found_clients = []

        for client in clients:
            full_name = f"{client['name']} {client['last_name']}".lower()

            if search_text in full_name:
                found_clients.append(client)

        waiting_for_client_search = False

        if found_clients:
            await message.answer(
                format_clients_list("🔎 Найденные клиенты:", found_clients)
            )
        else:
            await message.answer("Клиенты не найдены.")