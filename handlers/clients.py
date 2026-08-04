from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from handlers.start import main_menu


router = Router()


clients = []


class ClientFlow(StatesGroup):
    waiting_for_name = State()
    waiting_for_last_name = State()
    waiting_for_phone = State()
    waiting_for_instagram = State()
    waiting_for_email = State()
    waiting_for_notes = State()
    waiting_for_delete = State()
    waiting_for_edit_name = State()
    waiting_for_edit_field = State()
    waiting_for_edit_value = State()
    waiting_for_search = State()
    waiting_for_card = State()


clients_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить клиента")],
        [KeyboardButton(text="📋 Список клиентов")],
        [KeyboardButton(text="👤 Карточка клиента")],
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
        if (
            client["name"].lower() == name.lower()
            and client["last_name"].lower() == last_name.lower()
        ):
            return client

    return None


def client_exists(name, last_name):
    return find_client_by_full_name(name, last_name) is not None


def format_client(client, number):
    return (
        f"{number}. {client['name']} {client['last_name']}\n"
        f"   Телефон: {client['phone']}\n"
        f"   Instagram: {client['instagram']}\n"
        f"   Email: {client['email']}\n"
        f"   Заметки: {client['notes']}\n\n"
    )


def format_client_card(client):
    return (
        "👤 Карточка клиента\n\n"
        f"Имя: {client['name']}\n"
        f"Фамилия: {client['last_name']}\n"
        f"Телефон: {client['phone']}\n"
        f"Instagram: {client['instagram']}\n"
        f"Email: {client['email']}\n"
        f"Заметки: {client['notes']}"
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
async def open_clients_menu(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    await message.answer(
        "👥 Раздел «Клиенты»\n\nВыбери действие:",
        reply_markup=clients_menu
    )


@router.message(F.text == "➕ Добавить клиента")
async def ask_client_name(
    message: Message,
    state: FSMContext,
):
    await state.clear()
    await state.set_state(ClientFlow.waiting_for_name)
    await state.update_data(new_client={})

    await message.answer("Введите имя клиента:")


@router.message(F.text == "📋 Список клиентов")
async def show_clients(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    if clients:
        await message.answer(format_clients_list("📋 Список клиентов:", clients))
    else:
        await message.answer("Список клиентов пока пуст.")


@router.message(F.text == "👤 Карточка клиента")
async def ask_client_card(
    message: Message,
    state: FSMContext,
):
    await state.clear()
    await state.set_state(ClientFlow.waiting_for_card)

    await message.answer("Введите имя и фамилию клиента через пробел:")


@router.message(F.text == "❌ Удалить клиента")
async def ask_client_to_delete(
    message: Message,
    state: FSMContext,
):
    await state.clear()
    await state.set_state(ClientFlow.waiting_for_delete)

    await message.answer("Введите имя и фамилию клиента через пробел:")


@router.message(F.text == "✏️ Редактировать клиента")
async def ask_client_to_edit(
    message: Message,
    state: FSMContext,
):
    await state.clear()
    await state.set_state(ClientFlow.waiting_for_edit_name)

    await message.answer("Введите имя и фамилию клиента через пробел:")


@router.message(F.text == "🔎 Найти клиента")
async def ask_client_to_search(
    message: Message,
    state: FSMContext,
):
    await state.clear()
    await state.set_state(ClientFlow.waiting_for_search)

    await message.answer("Введите имя, фамилию или часть текста для поиска:")


@router.message(
    StateFilter(ClientFlow),
    F.text == "⬅️ Назад",
)
async def back(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    await message.answer(
        "Главное меню:",
        reply_markup=main_menu
    )


@router.message(StateFilter(ClientFlow))
async def handle_client_text(
    message: Message,
    state: FSMContext,
):
    current_state = await state.get_state()
    data = await state.get_data()

    if current_state == ClientFlow.waiting_for_name.state:
        new_client = data.get("new_client", {})
        new_client["name"] = message.text

        await state.update_data(new_client=new_client)
        await state.set_state(ClientFlow.waiting_for_last_name)

        await message.answer("Введите фамилию клиента:")

    elif current_state == ClientFlow.waiting_for_last_name.state:
        new_client = data.get("new_client", {})
        new_client["last_name"] = message.text

        if client_exists(new_client["name"], new_client["last_name"]):
            await state.clear()

            await message.answer("Такой клиент уже существует.")
        else:
            await state.update_data(new_client=new_client)
            await state.set_state(ClientFlow.waiting_for_phone)

            await message.answer("Введите телефон клиента:")

    elif current_state == ClientFlow.waiting_for_phone.state:
        new_client = data.get("new_client", {})
        new_client["phone"] = message.text

        await state.update_data(new_client=new_client)
        await state.set_state(ClientFlow.waiting_for_instagram)

        await message.answer("Введите Instagram клиента:")

    elif current_state == ClientFlow.waiting_for_instagram.state:
        new_client = data.get("new_client", {})
        new_client["instagram"] = message.text

        await state.update_data(new_client=new_client)
        await state.set_state(ClientFlow.waiting_for_email)

        await message.answer("Введите email клиента:")

    elif current_state == ClientFlow.waiting_for_email.state:
        new_client = data.get("new_client", {})
        new_client["email"] = message.text

        await state.update_data(new_client=new_client)
        await state.set_state(ClientFlow.waiting_for_notes)

        await message.answer("Введите заметки о клиенте:")

    elif current_state == ClientFlow.waiting_for_notes.state:
        new_client = data.get("new_client", {})
        new_client["notes"] = message.text

        clients.append(new_client)
        save_clients()

        full_name = f"{new_client['name']} {new_client['last_name']}"

        await state.clear()

        await message.answer(f"✅ Клиент «{full_name}» добавлен.")

    elif current_state == ClientFlow.waiting_for_card.state:
        parts = message.text.split(maxsplit=1)

        if len(parts) < 2:
            await message.answer("Введите и имя, и фамилию клиента.")
        else:
            name = parts[0]
            last_name = parts[1]
            client = find_client_by_full_name(name, last_name)

            if client:
                await message.answer(format_client_card(client))
            else:
                await message.answer(f"Клиент «{name} {last_name}» не найден.")

            await state.clear()

    elif current_state == ClientFlow.waiting_for_delete.state:
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

            await state.clear()

    elif current_state == ClientFlow.waiting_for_edit_name.state:
        parts = message.text.split(maxsplit=1)

        if len(parts) < 2:
            await message.answer("Введите и имя, и фамилию клиента.")
        else:
            name = parts[0]
            last_name = parts[1]
            client = find_client_by_full_name(name, last_name)

            if client:
                await state.update_data(
                    client_name=name,
                    client_last_name=last_name,
                )
                await state.set_state(
                    ClientFlow.waiting_for_edit_field
                )

                await message.answer(
                    "Что нужно изменить?",
                    reply_markup=edit_fields_menu
                )
            else:
                await state.clear()

                await message.answer(f"Клиент «{name} {last_name}» не найден.")

    elif current_state == ClientFlow.waiting_for_edit_field.state:
        field_name = message.text
        field_key = get_field_key(field_name)

        if field_key:
            await state.update_data(field_to_edit=field_key)
            await state.set_state(
                ClientFlow.waiting_for_edit_value
            )

            await message.answer(f"Введите новое значение для поля «{field_name}»:")
        else:
            await message.answer("Такого поля нет. Выберите поле из меню.")

    elif current_state == ClientFlow.waiting_for_edit_value.state:
        new_value = message.text
        client_to_edit = find_client_by_full_name(
            data.get("client_name", ""),
            data.get("client_last_name", ""),
        )
        field_to_edit = data.get("field_to_edit", "")

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

        await state.clear()

    elif current_state == ClientFlow.waiting_for_search.state:
        search_text = message.text.lower()
        found_clients = []

        for client in clients:
            full_name = f"{client['name']} {client['last_name']}".lower()

            if search_text in full_name:
                found_clients.append(client)

        await state.clear()

        if found_clients:
            await message.answer(
                format_clients_list("🔎 Найденные клиенты:", found_clients)
            )
        else:
            await message.answer("Клиенты не найдены.")
