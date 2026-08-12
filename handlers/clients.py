from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from handlers.start import main_menu
from services import clients as clients_service


router = Router()


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
    return clients_service.load_clients()


def find_client_by_full_name(name, last_name):
    return clients_service.get_client_by_full_name(
        name,
        last_name,
    )


def client_exists(name, last_name):
    return clients_service.current_client_exists(
        name,
        last_name,
    )


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
    return clients_service.get_field_key(field_name)


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
    clients = load_clients()

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

        creation_status = clients_service.create_client(
            new_client
        )

        full_name = f"{new_client['name']} {new_client['last_name']}"

        await state.clear()

        if creation_status == clients_service.CLIENT_DUPLICATE:
            await message.answer("Такой клиент уже существует.")
        else:
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
            deletion_status = clients_service.delete_client(
                name,
                last_name,
            )

            if deletion_status == clients_service.CLIENT_DELETED:
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
        client_name = data.get("client_name", "")
        client_last_name = data.get("client_last_name", "")
        field_to_edit = data.get("field_to_edit", "")
        (
            edit_status,
            client_to_edit,
        ) = clients_service.edit_client_field(
            client_name,
            client_last_name,
            field_to_edit,
            new_value,
        )

        if edit_status == clients_service.CLIENT_DUPLICATE:
            if field_to_edit == "name":
                await message.answer(
                    f"Клиент «{new_value} {client_to_edit['last_name']}» уже существует.",
                    reply_markup=clients_menu
                )
            else:
                await message.answer(
                    f"Клиент «{client_to_edit['name']} {new_value}» уже существует.",
                    reply_markup=clients_menu
                )

        elif edit_status == clients_service.CLIENT_NOT_FOUND:
            await message.answer(
                "Клиент не найден.",
                reply_markup=clients_menu
            )

        else:
            await message.answer(
                "✅ Данные клиента обновлены.",
                reply_markup=clients_menu
            )

        await state.clear()

    elif current_state == ClientFlow.waiting_for_search.state:
        found_clients = clients_service.search_clients(
            message.text
        )

        await state.clear()

        if found_clients:
            await message.answer(
                format_clients_list("🔎 Найденные клиенты:", found_clients)
            )
        else:
            await message.answer("Клиенты не найдены.")
