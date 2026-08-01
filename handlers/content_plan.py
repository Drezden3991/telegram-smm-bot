import asyncio

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)
from openai.types.responses import (
    EasyInputMessageParam,
    ResponseInputParam,
)
from openai.types.shared.reasoning_effort import ReasoningEffort
from openai.types.shared_params.reasoning import Reasoning
from pydantic import BaseModel, Field, ValidationError

from handlers.start import main_menu


router = Router()

CONTENT_PLANS_FILE = "content_plans.txt"
CLIENTS_FILE = "clients.txt"

SEPARATOR = "-" * 40

OPENAI_MODEL = "gpt-5.6"
OPENAI_REASONING_EFFORT: ReasoningEffort = "low"
OPENAI_TIMEOUT_SECONDS = 45.0

MAX_BRIEF_LENGTH = 500
TELEGRAM_MESSAGE_LIMIT = 4096

WITHOUT_CLIENT_BUTTON = "🚫 Без клиента"
BACK_BUTTON = "⬅️ Назад"

CONTENT_PLAN_INSTRUCTIONS = (
    "Ты опытный SMM-стратег для Telegram. Создай практичный контент-план "
    "ровно на семь дней по пользовательскому брифу. Дни должны идти строго "
    "от 1 до 7 без повторов. Для каждого дня сформулируй отдельные цель, тему, "
    "формат публикации, ключевой тезис и призыв к действию. Соблюдай логику "
    "прогрева: знакомство и польза в начале, доверие и работа с возражениями "
    "в середине, целевое действие ближе к концу. Чередуй подходящие для Telegram "
    "форматы. Пиши на русском языке, конкретно и кратко. Не добавляй поля, "
    "которых нет в схеме, и не изменяй данные пользовательского брифа."
)


class ContentPlanDay(BaseModel):
    day: int = Field(ge=1, le=7)
    goal: str = Field(min_length=1, max_length=50)
    topic: str = Field(min_length=1, max_length=90)
    format: str = Field(min_length=1, max_length=30)
    key_message: str = Field(min_length=1, max_length=120)
    cta: str = Field(min_length=1, max_length=70)


class SevenDayContentPlan(BaseModel):
    days: list[ContentPlanDay] = Field(
        min_length=7,
        max_length=7,
    )


class ContentPlanGenerationError(Exception):
    pass


class CreateContentPlan(StatesGroup):
    waiting_for_client = State()
    waiting_for_brief = State()


class SearchContentPlan(StatesGroup):
    waiting_for_query = State()


class DeleteContentPlan(StatesGroup):
    waiting_for_number = State()


class EditContentPlan(StatesGroup):
    waiting_for_number = State()
    waiting_for_client = State()
    waiting_for_new_brief = State()


content_plan_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Создать контент-план")],
        [KeyboardButton(text="📋 Мои контент-планы")],
        [KeyboardButton(text="🔍 Найти контент-план")],
        [KeyboardButton(text="✏️ Редактировать контент-план")],
        [KeyboardButton(text="🗑 Удалить контент-план")],
        [KeyboardButton(text=BACK_BUTTON)],
    ],
    resize_keyboard=True,
)


def read_content_plans():
    try:
        with open(
            CONTENT_PLANS_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            content = file.read().strip()

    except FileNotFoundError:
        return []

    if not content:
        return []

    content_plans = content.split(SEPARATOR)

    return [
        content_plan.strip()
        for content_plan in content_plans
        if content_plan.strip()
    ]


def save_content_plans(content_plans):
    with open(
        CONTENT_PLANS_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        for content_plan in content_plans:
            file.write(content_plan.strip())
            file.write("\n")
            file.write(SEPARATOR)
            file.write("\n")


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


def load_clients():
    loaded_clients = []

    try:
        with open(
            CLIENTS_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            for line in file:
                line = line.strip()

                if line:
                    loaded_clients.append(
                        create_client_from_line(line)
                    )

    except FileNotFoundError:
        pass

    return loaded_clients


def get_client_full_name(client):
    name = client.get("name", "").strip()
    last_name = client.get("last_name", "").strip()

    return f"{name} {last_name}".strip()


def create_clients_menu(clients):
    keyboard = []

    for number, client in enumerate(clients, start=1):
        full_name = get_client_full_name(client)

        keyboard.append(
            [
                KeyboardButton(
                    text=f"{number}. {full_name}"
                )
            ]
        )

    keyboard.append(
        [KeyboardButton(text=WITHOUT_CLIENT_BUTTON)]
    )
    keyboard.append(
        [KeyboardButton(text=BACK_BUTTON)]
    )

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
    )


def get_selected_client(message_text, clients):
    for number, client in enumerate(clients, start=1):
        full_name = get_client_full_name(client)
        expected_text = f"{number}. {full_name}"

        if message_text == expected_text:
            return client

    return None


def build_client_ai_context(client):
    if not client:
        return ""

    context_parts = []

    full_name = get_client_full_name(client)

    if full_name:
        context_parts.append(
            f"Название или имя клиента: {full_name}"
        )

    instagram = client.get("instagram", "").strip()

    if instagram and instagram != "-":
        context_parts.append(
            f"Instagram клиента: {instagram}"
        )

    notes = client.get("notes", "").strip()

    if notes and notes != "-":
        context_parts.append(
            f"Информация о клиенте: {notes}"
        )

    if not context_parts:
        return ""

    return "\n".join(context_parts)


def build_ai_brief(client, user_brief):
    client_context = build_client_ai_context(client)

    if not client_context:
        return user_brief

    return (
        f"Карточка клиента:\n"
        f"{client_context}\n\n"
        f"Задача пользователя:\n"
        f"{user_brief}"
    )


def generate_ai_content_plan(brief):
    try:
        client = OpenAI(
            timeout=OPENAI_TIMEOUT_SECONDS,
            max_retries=1,
        )

        response_input: ResponseInputParam = [
            EasyInputMessageParam(
                role="developer",
                content=CONTENT_PLAN_INSTRUCTIONS,
            ),
            EasyInputMessageParam(
                role="user",
                content=(
                    "Краткий бриф пользователя:\n"
                    f"{brief}"
                ),
            ),
        ]

        response = client.responses.parse(
            model=OPENAI_MODEL,
            reasoning=Reasoning(
                effort=OPENAI_REASONING_EFFORT,
            ),
            input=response_input,
            text_format=SevenDayContentPlan,
        )

    except AuthenticationError as error:
        raise ContentPlanGenerationError(
            "Не удалось авторизоваться в OpenAI. "
            "Проверьте настройку API и повторите позже."
        ) from error

    except RateLimitError as error:
        raise ContentPlanGenerationError(
            "OpenAI временно ограничил число запросов. "
            "Попробуйте ещё раз немного позже."
        ) from error

    except (
        APITimeoutError,
        APIConnectionError,
    ) as error:
        raise ContentPlanGenerationError(
            "OpenAI сейчас не отвечает. "
            "Проверьте интернет-соединение "
            "и попробуйте ещё раз."
        ) from error

    except APIStatusError as error:
        raise ContentPlanGenerationError(
            "OpenAI вернул ошибку сервиса. "
            "Контент-план не сохранён; "
            "попробуйте позже."
        ) from error

    except OpenAIError as error:
        raise ContentPlanGenerationError(
            "Не удалось получить ответ OpenAI. "
            "Контент-план не сохранён; "
            "попробуйте позже."
        ) from error

    except (
        ValidationError,
        ValueError,
    ) as error:
        raise ContentPlanGenerationError(
            "OpenAI вернул неполный контент-план. "
            "Ничего не сохранено; "
            "попробуйте ещё раз."
        ) from error

    content_plan = response.output_parsed

    if content_plan is None:
        raise ContentPlanGenerationError(
            "OpenAI не сформировал контент-план. "
            "Ничего не сохранено; "
            "попробуйте ещё раз."
        )

    days = [
        item.day
        for item in content_plan.days
    ]

    if days != list(range(1, 8)):
        raise ContentPlanGenerationError(
            "OpenAI вернул дни в неверном порядке. "
            "Ничего не сохранено; "
            "попробуйте ещё раз."
        )

    return content_plan


def format_content_plan_text(
    client_name,
    user_brief,
    content_plan,
):
    result = "📅 AI-контент-план на 7 дней\n\n"

    if client_name:
        result += f"Клиент: {client_name}\n"

    result += f"Бриф: {user_brief}\n\n"

    for item in content_plan.days:
        result += (
            f"День {item.day}\n"
            f"🎯 Цель: {item.goal}\n"
            f"📝 Тема: {item.topic}\n"
            f"📌 Формат: {item.format}\n"
            f"💬 Ключевой тезис: "
            f"{item.key_message}\n"
            f"👉 CTA: {item.cta}\n\n"
        )

    return result.strip()


async def build_content_plan_text(
    client,
    user_brief,
):
    ai_brief = build_ai_brief(
        client,
        user_brief,
    )

    content_plan = await asyncio.to_thread(
        generate_ai_content_plan,
        ai_brief,
    )

    client_name = ""

    if client:
        client_name = get_client_full_name(client)

    return format_content_plan_text(
        client_name,
        user_brief,
        content_plan,
    )


def format_content_plans_list(content_plans):
    result = "📋 Мои контент-планы:\n\n"

    for index, content_plan in enumerate(
        content_plans,
        start=1,
    ):
        result += (
            f"№ {index}\n"
            f"{content_plan}\n\n"
        )

    return result


def split_text_for_telegram(
    text: str,
    max_length: int = TELEGRAM_MESSAGE_LIMIT,
) -> list[str]:
    if max_length < 1:
        raise ValueError(
            "max_length must be greater than zero"
        )

    chunks = []
    remaining_text = text

    while len(remaining_text) > max_length:
        split_position = remaining_text.rfind(
            "\n",
            0,
            max_length,
        )

        if split_position > 0:
            split_position += 1

        else:
            split_position = remaining_text.rfind(
                " ",
                0,
                max_length,
            )

            if split_position > 0:
                split_position += 1
            else:
                split_position = max_length

        chunks.append(
            remaining_text[:split_position]
        )

        remaining_text = remaining_text[
            split_position:
        ]

    if remaining_text:
        chunks.append(remaining_text)

    return chunks


async def send_long_message(
    message: Message,
    text: str,
    reply_markup: ReplyKeyboardMarkup | None = None,
) -> None:
    chunks = split_text_for_telegram(text)

    for index, chunk in enumerate(chunks):
        is_last_chunk = index == len(chunks) - 1

        if reply_markup is not None and is_last_chunk:
            await message.answer(
                chunk,
                reply_markup=reply_markup,
            )
        else:
            await message.answer(chunk)


async def show_client_selection(message):
    clients = load_clients()
    clients_menu = create_clients_menu(clients)

    if clients:
        await message.answer(
            "👥 Выбери клиента для контент-плана:",
            reply_markup=clients_menu,
        )

    else:
        await message.answer(
            "Сохранённых клиентов пока нет.\n\n"
            "Можно создать контент-план без клиента:",
            reply_markup=clients_menu,
        )


async def ask_for_brief(message):
    await message.answer(
        "Введите краткий бриф для контент-плана "
        "одним сообщением:\n\n"
        "• продукт или услуга;\n"
        "• целевая аудитория;\n"
        "• цель продвижения;\n"
        "• дополнительные пожелания.\n\n"
        f"Максимум {MAX_BRIEF_LENGTH} символов.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=BACK_BUTTON)]
            ],
            resize_keyboard=True,
        ),
    )


@router.message(F.text == "📅 Контент-план")
async def open_content_plan_menu(message: Message):
    await message.answer(
        "📅 Раздел «Контент-план»\n\n"
        "Выбери действие:",
        reply_markup=content_plan_menu,
    )


@router.message(F.text == "📅 Создать контент-план")
async def start_content_plan_creation(
    message: Message,
    state: FSMContext,
):
    await state.clear()
    await state.set_state(
        CreateContentPlan.waiting_for_client
    )

    await show_client_selection(message)


@router.message(
    CreateContentPlan.waiting_for_client,
    F.text == BACK_BUTTON,
)
async def cancel_create_client_selection(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    await message.answer(
        "📅 Раздел «Контент-план»\n\n"
        "Выбери действие:",
        reply_markup=content_plan_menu,
    )


@router.message(
    CreateContentPlan.waiting_for_client
)
async def select_client_for_new_plan(
    message: Message,
    state: FSMContext,
):
    selected_text = message.text.strip()
    clients = load_clients()

    if selected_text == WITHOUT_CLIENT_BUTTON:
        await state.update_data(
            selected_client=None
        )

    else:
        selected_client = get_selected_client(
            selected_text,
            clients,
        )

        if selected_client is None:
            await message.answer(
                "Пожалуйста, выбери клиента "
                "кнопкой ниже.",
                reply_markup=create_clients_menu(
                    clients
                ),
            )
            return

        await state.update_data(
            selected_client=selected_client
        )

    await state.set_state(
        CreateContentPlan.waiting_for_brief
    )

    await ask_for_brief(message)


@router.message(
    CreateContentPlan.waiting_for_brief,
    F.text == BACK_BUTTON,
)
async def back_to_create_client_selection(
    message: Message,
    state: FSMContext,
):
    await state.set_state(
        CreateContentPlan.waiting_for_client
    )

    await show_client_selection(message)


@router.message(
    CreateContentPlan.waiting_for_brief
)
async def create_content_plan(
    message: Message,
    state: FSMContext,
):
    user_brief = message.text.strip()

    if not user_brief:
        await message.answer(
            "Бриф не может быть пустым. "
            "Введите данные для контент-плана:"
        )
        return

    if len(user_brief) > MAX_BRIEF_LENGTH:
        await message.answer(
            "Бриф слишком длинный. "
            f"Сократите его до "
            f"{MAX_BRIEF_LENGTH} символов:"
        )
        return

    data = await state.get_data()
    selected_client = data.get(
        "selected_client"
    )

    await message.answer(
        "⏳ Создаю контент-план "
        "с помощью GPT-5.6..."
    )

    try:
        content_plan = await build_content_plan_text(
            selected_client,
            user_brief,
        )

    except ContentPlanGenerationError as error:
        await state.clear()

        await message.answer(
            str(error),
            reply_markup=content_plan_menu,
        )
        return

    content_plans = read_content_plans()
    content_plans.append(content_plan)

    save_content_plans(content_plans)

    await state.clear()

    await send_long_message(
        message,
        content_plan,
    )

    await message.answer(
        "✅ Контент-план успешно сохранён.",
        reply_markup=content_plan_menu,
    )


@router.message(F.text == "📋 Мои контент-планы")
async def show_content_plans(message: Message):
    content_plans = read_content_plans()

    if not content_plans:
        await message.answer(
            "📭 У тебя пока нет "
            "сохранённых контент-планов.",
            reply_markup=content_plan_menu,
        )
        return

    await send_long_message(
        message,
        format_content_plans_list(
            content_plans
        ),
        reply_markup=content_plan_menu,
    )


@router.message(F.text == "🔍 Найти контент-план")
async def ask_search_query(
    message: Message,
    state: FSMContext,
):
    await state.set_state(
        SearchContentPlan.waiting_for_query
    )

    await message.answer(
        "Введите слово, тему "
        "или имя клиента для поиска:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=BACK_BUTTON)]
            ],
            resize_keyboard=True,
        ),
    )


@router.message(
    SearchContentPlan.waiting_for_query,
    F.text == BACK_BUTTON,
)
async def cancel_search(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    await message.answer(
        "📅 Раздел «Контент-план»\n\n"
        "Выбери действие:",
        reply_markup=content_plan_menu,
    )


@router.message(
    SearchContentPlan.waiting_for_query
)
async def search_content_plan(
    message: Message,
    state: FSMContext,
):
    query = message.text.strip().lower()
    content_plans = read_content_plans()

    found_content_plans = [
        content_plan
        for content_plan in content_plans
        if query in content_plan.lower()
    ]

    await state.clear()

    if not found_content_plans:
        await message.answer(
            "Ничего не найдено.",
            reply_markup=content_plan_menu,
        )
        return

    await send_long_message(
        message,
        format_content_plans_list(
            found_content_plans
        ),
        reply_markup=content_plan_menu,
    )


@router.message(F.text == "🗑 Удалить контент-план")
async def ask_delete_content_plan_number(
    message: Message,
    state: FSMContext,
):
    content_plans = read_content_plans()

    if not content_plans:
        await message.answer(
            "📭 У тебя пока нет "
            "сохранённых контент-планов.",
            reply_markup=content_plan_menu,
        )
        return

    await state.set_state(
        DeleteContentPlan.waiting_for_number
    )

    await send_long_message(
        message,
        format_content_plans_list(
            content_plans
        )
        + "Введите номер контент-плана, "
        + "который нужно удалить:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=BACK_BUTTON)]
            ],
            resize_keyboard=True,
        ),
    )


@router.message(
    DeleteContentPlan.waiting_for_number,
    F.text == BACK_BUTTON,
)
async def cancel_delete(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    await message.answer(
        "📅 Раздел «Контент-план»\n\n"
        "Выбери действие:",
        reply_markup=content_plan_menu,
    )


@router.message(
    DeleteContentPlan.waiting_for_number
)
async def delete_content_plan(
    message: Message,
    state: FSMContext,
):
    content_plans = read_content_plans()
    number_text = message.text.strip()

    if not number_text.isdigit():
        await message.answer(
            "Введите номер контент-плана цифрой:"
        )
        return

    number = int(number_text)

    if (
        number < 1
        or number > len(content_plans)
    ):
        await message.answer(
            "Контент-плана с таким номером нет. "
            "Введите корректный номер:"
        )
        return

    deleted_content_plan = content_plans.pop(
        number - 1
    )

    save_content_plans(content_plans)

    await state.clear()

    await send_long_message(
        message,
        "🗑 Контент-план удалён:\n\n"
        f"{deleted_content_plan}",
        reply_markup=content_plan_menu,
    )


@router.message(
    F.text == "✏️ Редактировать контент-план"
)
async def ask_edit_content_plan_number(
    message: Message,
    state: FSMContext,
):
    content_plans = read_content_plans()

    if not content_plans:
        await message.answer(
            "📭 У тебя пока нет "
            "сохранённых контент-планов.",
            reply_markup=content_plan_menu,
        )
        return

    await state.set_state(
        EditContentPlan.waiting_for_number
    )

    await send_long_message(
        message,
        format_content_plans_list(
            content_plans
        )
        + "Введите номер контент-плана, "
        + "который нужно отредактировать:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=BACK_BUTTON)]
            ],
            resize_keyboard=True,
        ),
    )


@router.message(
    EditContentPlan.waiting_for_number,
    F.text == BACK_BUTTON,
)
async def cancel_edit_number(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    await message.answer(
        "📅 Раздел «Контент-план»\n\n"
        "Выбери действие:",
        reply_markup=content_plan_menu,
    )


@router.message(
    EditContentPlan.waiting_for_number
)
async def select_content_plan_for_edit(
    message: Message,
    state: FSMContext,
):
    content_plans = read_content_plans()
    number_text = message.text.strip()

    if not number_text.isdigit():
        await message.answer(
            "Введите номер контент-плана цифрой:"
        )
        return

    number = int(number_text)

    if (
        number < 1
        or number > len(content_plans)
    ):
        await message.answer(
            "Контент-плана с таким номером нет. "
            "Введите корректный номер:"
        )
        return

    await state.update_data(
        content_plan_number=number
    )

    await state.set_state(
        EditContentPlan.waiting_for_client
    )

    await show_client_selection(message)


@router.message(
    EditContentPlan.waiting_for_client,
    F.text == BACK_BUTTON,
)
async def back_to_edit_number(
    message: Message,
    state: FSMContext,
):
    content_plans = read_content_plans()

    await state.set_state(
        EditContentPlan.waiting_for_number
    )

    await send_long_message(
        message,
        format_content_plans_list(
            content_plans
        )
        + "Введите номер контент-плана, "
        + "который нужно отредактировать:",
    )


@router.message(
    EditContentPlan.waiting_for_client
)
async def select_client_for_edit(
    message: Message,
    state: FSMContext,
):
    selected_text = message.text.strip()
    clients = load_clients()

    if selected_text == WITHOUT_CLIENT_BUTTON:
        await state.update_data(
            selected_client=None
        )

    else:
        selected_client = get_selected_client(
            selected_text,
            clients,
        )

        if selected_client is None:
            await message.answer(
                "Пожалуйста, выбери клиента "
                "кнопкой ниже.",
                reply_markup=create_clients_menu(
                    clients
                ),
            )
            return

        await state.update_data(
            selected_client=selected_client
        )

    await state.set_state(
        EditContentPlan.waiting_for_new_brief
    )

    await message.answer(
        "Введите новый краткий бриф "
        "для AI-контент-плана "
        f"(до {MAX_BRIEF_LENGTH} символов):",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=BACK_BUTTON)]
            ],
            resize_keyboard=True,
        ),
    )


@router.message(
    EditContentPlan.waiting_for_new_brief,
    F.text == BACK_BUTTON,
)
async def back_to_edit_client_selection(
    message: Message,
    state: FSMContext,
):
    await state.set_state(
        EditContentPlan.waiting_for_client
    )

    await show_client_selection(message)


@router.message(
    EditContentPlan.waiting_for_new_brief
)
async def edit_content_plan(
    message: Message,
    state: FSMContext,
):
    new_brief = message.text.strip()

    if not new_brief:
        await message.answer(
            "Бриф не может быть пустым. "
            "Введите новый бриф:"
        )
        return

    if len(new_brief) > MAX_BRIEF_LENGTH:
        await message.answer(
            "Бриф слишком длинный. "
            f"Сократите его до "
            f"{MAX_BRIEF_LENGTH} символов:"
        )
        return

    data = await state.get_data()

    number = data.get(
        "content_plan_number"
    )

    selected_client = data.get(
        "selected_client"
    )

    content_plans = read_content_plans()

    if (
        number is None
        or number < 1
        or number > len(content_plans)
    ):
        await state.clear()

        await message.answer(
            "Выбранный контент-план "
            "больше не найден.",
            reply_markup=content_plan_menu,
        )
        return

    await message.answer(
        "⏳ Обновляю контент-план "
        "с помощью GPT-5.6..."
    )

    try:
        updated_content_plan = (
            await build_content_plan_text(
                selected_client,
                new_brief,
            )
        )

    except ContentPlanGenerationError as error:
        await state.clear()

        await message.answer(
            str(error),
            reply_markup=content_plan_menu,
        )
        return

    content_plans[number - 1] = (
        updated_content_plan
    )

    save_content_plans(content_plans)

    await state.clear()

    await send_long_message(
        message,
        "✅ Контент-план успешно обновлён:\n\n"
        f"{updated_content_plan}",
        reply_markup=content_plan_menu,
    )


@router.message(F.text == BACK_BUTTON)
async def back(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    await message.answer(
        "Главное меню:",
        reply_markup=main_menu,
    )