import asyncio

from aiogram import F, Router
from aiogram.filters import StateFilter
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
from pydantic import ValidationError

from handlers.start import main_menu
from models.content_plan import ContentPlanDay, SevenDayContentPlan


router = Router()

CONTENT_PLANS_FILE = "content_plans.txt"
CLIENTS_FILE = "clients.txt"
POST_IDEAS_FILE = "post_ideas.txt"

SEPARATOR = "-" * 40

OPENAI_MODEL = "gpt-5.6"
OPENAI_REASONING_EFFORT: ReasoningEffort = "low"
OPENAI_TIMEOUT_SECONDS = 45.0

MAX_BRIEF_LENGTH = 500
TELEGRAM_MESSAGE_LIMIT = 4096
CONTENT_PLAN_SHORT_TITLE_MAX_LENGTH = 80
CONTENT_PLAN_CLIENT_TITLE_MAX_LENGTH = 30

WITHOUT_CLIENT_BUTTON = "🚫 Без клиента"
SKIP_IDEAS_BUTTON = "⏭ Пропустить идеи"
FINISH_IDEAS_BUTTON = "✅ Готово"
BACK_BUTTON = "⬅️ Назад"
CONFIRM_DELETE_BUTTON = "✅ Да, удалить"
CANCEL_DELETE_BUTTON = "❌ Отмена"

CONTENT_PLAN_INSTRUCTIONS = (
    "Ты опытный SMM-стратег для Telegram. Создай практичный контент-план "
    "ровно на семь дней по пользовательскому брифу. Дни должны идти строго "
    "от 1 до 7 без повторов. Для каждого дня сформулируй отдельные цель, тему, "
    "формат публикации, ключевой тезис и призыв к действию. Соблюдай логику "
    "прогрева: знакомство и польза в начале, доверие и работа с возражениями "
    "в середине, целевое действие ближе к концу. Чередуй подходящие для Telegram "
    "форматы. Если пользователь передал сохранённые идеи постов, используй их "
    "как дополнительный контекст и органично распределяй подходящие идеи по дням. "
    "Пиши на русском языке, конкретно и кратко. Не добавляй поля, которых нет "
    "в схеме, и не изменяй данные пользовательского брифа."
)


class ContentPlanGenerationError(Exception):
    pass


class CreateContentPlan(StatesGroup):
    waiting_for_client = State()
    waiting_for_ideas = State()
    waiting_for_brief = State()


class SearchContentPlan(StatesGroup):
    waiting_for_query = State()


class DeleteContentPlan(StatesGroup):
    waiting_for_number = State()
    waiting_for_confirmation = State()


class EditContentPlan(StatesGroup):
    waiting_for_number = State()
    waiting_for_client = State()
    waiting_for_ideas = State()
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


def load_post_ideas():
    try:
        with open(
            POST_IDEAS_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            return [
                line.strip()
                for line in file
                if line.strip()
            ]

    except FileNotFoundError:
        return []


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


def create_idea_button_text(
    number,
    is_selected,
):
    selection_mark = "✅" if is_selected else "▫️"

    return f"{selection_mark} {number}"


def create_ideas_menu(
    post_ideas,
    selected_ideas,
):
    keyboard = []
    idea_buttons = []

    for number, idea in enumerate(
        post_ideas,
        start=1,
    ):
        idea_buttons.append(
            KeyboardButton(
                text=create_idea_button_text(
                    number,
                    idea in selected_ideas,
                )
            )
        )

    for start in range(0, len(idea_buttons), 3):
        keyboard.append(
            idea_buttons[start:start + 3]
        )

    if post_ideas:
        keyboard.append(
            [KeyboardButton(text=FINISH_IDEAS_BUTTON)]
        )

    keyboard.append(
        [KeyboardButton(text=SKIP_IDEAS_BUTTON)]
    )
    keyboard.append(
        [KeyboardButton(text=BACK_BUTTON)]
    )

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
    )


def get_selected_idea_number(
    message_text,
    ideas_count,
):
    parts = message_text.split()

    if len(parts) != 2:
        return None

    selection_mark, number_text = parts

    if selection_mark not in ("▫️", "✅"):
        return None

    if not number_text.isdigit():
        return None

    number = int(number_text)

    if number < 1 or number > ideas_count:
        return None

    return number


def format_numbered_ideas(post_ideas):
    return "\n".join(
        f"{number}. {idea}"
        for number, idea in enumerate(
            post_ideas,
            start=1,
        )
    )


def format_selected_ideas(
    post_ideas,
    selected_ideas,
):
    selected_lines = [
        f"{number}. {idea}"
        for number, idea in enumerate(
            post_ideas,
            start=1,
        )
        if idea in selected_ideas
    ]

    if not selected_lines:
        return "✅ Выбрано:\n\nПока ничего не выбрано."

    return "✅ Выбрано:\n\n" + "\n".join(
        selected_lines
    )


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


def build_ideas_ai_context(selected_ideas):
    if not selected_ideas:
        return ""

    result = "Сохранённые идеи постов:\n"

    for number, idea in enumerate(
        selected_ideas,
        start=1,
    ):
        result += f"{number}. {idea}\n"

    return result.strip()


def build_ai_brief(
    client,
    selected_ideas,
    user_brief,
):
    brief_parts = []

    client_context = build_client_ai_context(
        client
    )

    ideas_context = build_ideas_ai_context(
        selected_ideas
    )

    if client_context:
        brief_parts.append(
            "Карточка клиента:\n"
            f"{client_context}"
        )

    if ideas_context:
        brief_parts.append(ideas_context)

    brief_parts.append(
        "Задача пользователя:\n"
        f"{user_brief}"
    )

    return "\n\n".join(brief_parts)


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
    selected_ideas,
    user_brief,
    content_plan,
):
    result = "📅 AI-контент-план на 7 дней\n\n"

    if client_name:
        result += f"Клиент: {client_name}\n"

    if selected_ideas:
        result += "Выбранные идеи:\n"

        for number, idea in enumerate(
            selected_ideas,
            start=1,
        ):
            result += f"{number}. {idea}\n"

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
    selected_ideas,
    user_brief,
):
    ai_brief = build_ai_brief(
        client,
        selected_ideas,
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
        selected_ideas,
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


def shorten_content_plan_title_part(text, max_length):
    normalized_text = " ".join(text.split())

    if len(normalized_text) <= max_length:
        return normalized_text

    return normalized_text[:max_length - 1].rstrip() + "…"


def create_content_plan_short_title(content_plan):
    client_name = ""
    brief_parts = []
    content_lines = content_plan.splitlines()

    for index, line in enumerate(content_lines):
        stripped_line = line.strip()

        if stripped_line.startswith("Клиент:"):
            client_name = stripped_line.partition(":")[2].strip()

        if stripped_line.startswith("Бриф:"):
            first_brief_part = stripped_line.partition(":")[2].strip()

            if first_brief_part:
                brief_parts.append(first_brief_part)

            for continuation_line in content_lines[index + 1:]:
                continuation_line = continuation_line.strip()

                if not continuation_line:
                    break

                brief_parts.append(continuation_line)

            break

    client_title = shorten_content_plan_title_part(
        client_name or "Без клиента",
        CONTENT_PLAN_CLIENT_TITLE_MAX_LENGTH,
    )
    brief = " ".join(brief_parts) or "Без брифа"
    separator = " — "
    brief_max_length = (
        CONTENT_PLAN_SHORT_TITLE_MAX_LENGTH
        - len(client_title)
        - len(separator)
    )
    brief_title = shorten_content_plan_title_part(
        brief,
        brief_max_length,
    )

    return f"{client_title}{separator}{brief_title}"


def format_compact_content_plans_list(content_plans):
    lines = ["📋 Выбери контент-план:", ""]

    lines.extend(
        f"{number}. {create_content_plan_short_title(content_plan)}"
        for number, content_plan in enumerate(
            content_plans,
            start=1,
        )
    )

    return "\n".join(lines)


def create_content_plan_number_menu(content_plans_count):
    number_buttons = [
        KeyboardButton(text=str(number))
        for number in range(1, content_plans_count + 1)
    ]
    keyboard = [
        number_buttons[start:start + 3]
        for start in range(0, len(number_buttons), 3)
    ]
    keyboard.append([KeyboardButton(text=BACK_BUTTON)])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
    )


def get_selected_content_plan_number(
    message_text,
    content_plans_count,
):
    valid_button_texts = {
        str(number)
        for number in range(1, content_plans_count + 1)
    }

    if message_text not in valid_button_texts:
        return None

    return int(message_text)


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


async def show_content_plan_number_selection(
    message,
    state,
    content_plans,
    action_prompt,
):
    await state.update_data(
        content_plan_choices=content_plans
    )

    await send_long_message(
        message,
        f"{format_compact_content_plans_list(content_plans)}\n\n"
        f"{action_prompt}",
        reply_markup=create_content_plan_number_menu(
            len(content_plans)
        ),
    )


async def show_content_plan_menu(message, state):
    await state.clear()

    await message.answer(
        "📅 Раздел «Контент-план»\n\n"
        "Выбери действие:",
        reply_markup=content_plan_menu,
    )


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


async def show_idea_selection(
    message,
    state,
    selected_ideas,
    show_full_list=True,
    post_ideas=None,
):
    if post_ideas is None:
        post_ideas = load_post_ideas()

    post_ideas = list(post_ideas)
    selected_ideas = [
        idea
        for idea in selected_ideas
        if idea in post_ideas
    ]

    await state.update_data(
        post_idea_choices=post_ideas,
        selected_ideas=selected_ideas,
    )

    ideas_menu = create_ideas_menu(
        post_ideas,
        selected_ideas,
    )

    if not post_ideas:
        await message.answer(
            "Сохранённых идей пока нет.\n\n"
            "Нажми «Пропустить идеи», "
            "чтобы продолжить:",
            reply_markup=ideas_menu,
        )
        return

    if show_full_list:
        await send_long_message(
            message,
            "💡 Сохранённые идеи:\n\n"
            f"{format_numbered_ideas(post_ideas)}",
        )

    await message.answer(
        f"{format_selected_ideas(post_ideas, selected_ideas)}\n\n"
        "Нажми номер, чтобы выбрать или снять выбор.\n"
        "Когда закончишь, нажми «✅ Готово».\n"
        "Можно также пропустить этот шаг.",
        reply_markup=ideas_menu,
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


async def ask_for_new_brief(message):
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
    selected_text = (message.text or "").strip()
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

    await state.update_data(
        selected_ideas=[]
    )

    await state.set_state(
        CreateContentPlan.waiting_for_ideas
    )

    await show_idea_selection(
        message,
        state,
        [],
    )


@router.message(
    CreateContentPlan.waiting_for_ideas,
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
    CreateContentPlan.waiting_for_ideas
)
async def select_ideas_for_new_plan(
    message: Message,
    state: FSMContext,
):
    selected_text = (message.text or "").strip()
    current_post_ideas = load_post_ideas()

    data = await state.get_data()
    post_ideas = data.get(
        "post_idea_choices",
        current_post_ideas,
    )
    selected_ideas = list(
        data.get("selected_ideas", [])
    )

    if selected_text == SKIP_IDEAS_BUTTON:
        await state.update_data(
            selected_ideas=[]
        )

        await state.set_state(
            CreateContentPlan.waiting_for_brief
        )

        await ask_for_brief(message)
        return

    if selected_text == FINISH_IDEAS_BUTTON:
        missing_selected_ideas = [
            idea
            for idea in selected_ideas
            if idea not in current_post_ideas
        ]

        if missing_selected_ideas:
            selected_ideas = [
                idea
                for idea in selected_ideas
                if idea in current_post_ideas
            ]

            await state.update_data(
                selected_ideas=selected_ideas
            )

            await message.answer(
                "Список идей изменился. "
                "Выбери доступные идеи заново."
            )
            await show_idea_selection(
                message,
                state,
                selected_ideas,
                post_ideas=current_post_ideas,
            )
            return

        if not selected_ideas:
            await message.answer(
                "Сначала выбери хотя бы одну идею "
                "или нажми «Пропустить идеи».",
                reply_markup=create_ideas_menu(
                    post_ideas,
                    selected_ideas,
                ),
            )
            return

        await state.set_state(
            CreateContentPlan.waiting_for_brief
        )

        await ask_for_brief(message)
        return

    selected_number = get_selected_idea_number(
        selected_text,
        len(post_ideas),
    )

    if selected_number is None:
        await message.answer(
            "Пожалуйста, выбери идею "
            "кнопкой ниже.",
            reply_markup=create_ideas_menu(
                post_ideas,
                selected_ideas,
            ),
        )
        return

    selected_idea = post_ideas[selected_number - 1]

    if selected_idea not in current_post_ideas:
        selected_ideas = [
            idea
            for idea in selected_ideas
            if idea in current_post_ideas
        ]

        await state.update_data(
            selected_ideas=selected_ideas
        )

        await message.answer(
            "Список идей изменился. "
            "Выбери идею в обновлённом списке."
        )
        await show_idea_selection(
            message,
            state,
            selected_ideas,
            post_ideas=current_post_ideas,
        )
        return

    if selected_idea in selected_ideas:
        selected_ideas.remove(selected_idea)
    else:
        selected_ideas.append(selected_idea)

    await state.update_data(
        selected_ideas=selected_ideas
    )

    await show_idea_selection(
        message,
        state,
        selected_ideas,
        show_full_list=False,
        post_ideas=post_ideas,
    )


@router.message(
    CreateContentPlan.waiting_for_brief,
    F.text == BACK_BUTTON,
)
async def back_to_create_idea_selection(
    message: Message,
    state: FSMContext,
):
    data = await state.get_data()

    selected_ideas = data.get(
        "selected_ideas",
        [],
    )

    await state.set_state(
        CreateContentPlan.waiting_for_ideas
    )

    await show_idea_selection(
        message,
        state,
        selected_ideas,
    )


@router.message(
    CreateContentPlan.waiting_for_brief
)
async def create_content_plan(
    message: Message,
    state: FSMContext,
):
    user_brief = (message.text or "").strip()

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

    selected_ideas = data.get(
        "selected_ideas",
        [],
    )

    current_post_ideas = load_post_ideas()
    missing_selected_ideas = [
        idea
        for idea in selected_ideas
        if idea not in current_post_ideas
    ]

    if missing_selected_ideas:
        selected_ideas = [
            idea
            for idea in selected_ideas
            if idea in current_post_ideas
        ]

        await state.update_data(
            selected_ideas=selected_ideas
        )
        await state.set_state(
            CreateContentPlan.waiting_for_ideas
        )

        await message.answer(
            "Список идей изменился. "
            "Выбери доступные идеи заново."
        )
        await show_idea_selection(
            message,
            state,
            selected_ideas,
            post_ideas=current_post_ideas,
        )
        return

    await message.answer(
        "⏳ Создаю контент-план "
        "с помощью GPT-5.6..."
    )

    try:
        content_plan = await build_content_plan_text(
            selected_client,
            selected_ideas,
            user_brief,
        )

    except ContentPlanGenerationError as error:
        await state.clear()

        await message.answer(
            str(error),
            reply_markup=content_plan_menu,
        )
        return

    latest_post_ideas = load_post_ideas()
    missing_selected_ideas = [
        idea
        for idea in selected_ideas
        if idea not in latest_post_ideas
    ]

    if missing_selected_ideas:
        selected_ideas = [
            idea
            for idea in selected_ideas
            if idea in latest_post_ideas
        ]

        await state.update_data(
            selected_ideas=selected_ideas
        )
        await state.set_state(
            CreateContentPlan.waiting_for_ideas
        )

        await message.answer(
            "Список идей изменился во время создания. "
            "Контент-план не сохранён; выбери идеи заново."
        )
        await show_idea_selection(
            message,
            state,
            selected_ideas,
            post_ideas=latest_post_ideas,
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
        "Введите слово, тему, идею "
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
    query = (message.text or "").strip().lower()
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

    await show_content_plan_number_selection(
        message,
        state,
        content_plans,
        "Нажми номер плана, который нужно удалить.",
    )


@router.message(
    DeleteContentPlan.waiting_for_number,
    F.text == BACK_BUTTON,
)
async def cancel_delete(
    message: Message,
    state: FSMContext,
):
    await show_content_plan_menu(message, state)


@router.message(
    DeleteContentPlan.waiting_for_number
)
async def delete_content_plan(
    message: Message,
    state: FSMContext,
):
    content_plans = read_content_plans()
    selected_text = (message.text or "").strip()
    data = await state.get_data()
    displayed_content_plans = data.get(
        "content_plan_choices",
        [],
    )

    if content_plans != displayed_content_plans:
        if not content_plans:
            await state.clear()

            await message.answer(
                "📭 Список изменился, и сохранённых "
                "контент-планов больше нет.",
                reply_markup=content_plan_menu,
            )
            return

        await show_content_plan_number_selection(
            message,
            state,
            content_plans,
            "Список изменился. Нажми номер плана "
            "в обновлённом списке.",
        )
        return

    number = get_selected_content_plan_number(
        selected_text,
        len(displayed_content_plans),
    )

    if number is None:
        await message.answer(
            "Пожалуйста, выбери план кнопкой с номером ниже.",
            reply_markup=create_content_plan_number_menu(
                len(displayed_content_plans)
            ),
        )
        return

    selected_content_plan = content_plans[number - 1]

    await state.update_data(
        content_plan_number=number,
        selected_content_plan=selected_content_plan,
    )
    await state.set_state(
        DeleteContentPlan.waiting_for_confirmation
    )

    confirmation_menu = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=CONFIRM_DELETE_BUTTON),
                KeyboardButton(text=CANCEL_DELETE_BUTTON),
            ],
            [KeyboardButton(text=BACK_BUTTON)],
        ],
        resize_keyboard=True,
    )

    await send_long_message(
        message,
        "🗑 Выбран контент-план:\n\n"
        f"{selected_content_plan}\n\n"
        "Удалить этот контент-план?",
        reply_markup=confirmation_menu,
    )


@router.message(
    DeleteContentPlan.waiting_for_confirmation,
    F.text == BACK_BUTTON,
)
async def back_to_delete_number(
    message: Message,
    state: FSMContext,
):
    content_plans = read_content_plans()

    if not content_plans:
        await state.clear()

        await message.answer(
            "📭 Сохранённых контент-планов больше нет.",
            reply_markup=content_plan_menu,
        )
        return

    await state.set_state(
        DeleteContentPlan.waiting_for_number
    )

    await show_content_plan_number_selection(
        message,
        state,
        content_plans,
        "Нажми номер плана, который нужно удалить.",
    )


@router.message(
    DeleteContentPlan.waiting_for_confirmation,
    F.text == CANCEL_DELETE_BUTTON,
)
async def cancel_delete_confirmation(
    message: Message,
    state: FSMContext,
):
    await show_content_plan_menu(message, state)


@router.message(
    DeleteContentPlan.waiting_for_confirmation,
    F.text == CONFIRM_DELETE_BUTTON,
)
async def confirm_delete_content_plan(
    message: Message,
    state: FSMContext,
):
    data = await state.get_data()
    number = data.get("content_plan_number")
    selected_content_plan = data.get("selected_content_plan")
    content_plans = read_content_plans()

    if (
        number is None
        or number < 1
        or number > len(content_plans)
        or content_plans[number - 1] != selected_content_plan
    ):
        if not content_plans:
            await state.clear()

            await message.answer(
                "📭 Список изменился, и сохранённых "
                "контент-планов больше нет.",
                reply_markup=content_plan_menu,
            )
            return

        await state.set_state(
            DeleteContentPlan.waiting_for_number
        )

        await show_content_plan_number_selection(
            message,
            state,
            content_plans,
            "Список изменился. Выбери план заново.",
        )
        return

    deleted_content_plan = content_plans.pop(number - 1)

    save_content_plans(content_plans)
    await state.clear()

    await send_long_message(
        message,
        "🗑 Контент-план удалён:\n\n"
        f"{deleted_content_plan}",
        reply_markup=content_plan_menu,
    )


@router.message(
    DeleteContentPlan.waiting_for_confirmation
)
async def request_delete_confirmation_button(
    message: Message,
):
    await message.answer(
        "Подтверди удаление кнопкой ниже или вернись назад.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text=CONFIRM_DELETE_BUTTON),
                    KeyboardButton(text=CANCEL_DELETE_BUTTON),
                ],
                [KeyboardButton(text=BACK_BUTTON)],
            ],
            resize_keyboard=True,
        ),
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

    await show_content_plan_number_selection(
        message,
        state,
        content_plans,
        "Нажми номер плана, который нужно отредактировать.",
    )


@router.message(
    EditContentPlan.waiting_for_number,
    F.text == BACK_BUTTON,
)
async def cancel_edit_number(
    message: Message,
    state: FSMContext,
):
    await show_content_plan_menu(message, state)


@router.message(
    EditContentPlan.waiting_for_number
)
async def select_content_plan_for_edit(
    message: Message,
    state: FSMContext,
):
    content_plans = read_content_plans()
    selected_text = (message.text or "").strip()
    data = await state.get_data()
    displayed_content_plans = data.get(
        "content_plan_choices",
        [],
    )

    if content_plans != displayed_content_plans:
        if not content_plans:
            await state.clear()

            await message.answer(
                "📭 Список изменился, и сохранённых "
                "контент-планов больше нет.",
                reply_markup=content_plan_menu,
            )
            return

        await show_content_plan_number_selection(
            message,
            state,
            content_plans,
            "Список изменился. Нажми номер плана "
            "в обновлённом списке.",
        )
        return

    number = get_selected_content_plan_number(
        selected_text,
        len(displayed_content_plans),
    )

    if number is None:
        await message.answer(
            "Пожалуйста, выбери план кнопкой с номером ниже.",
            reply_markup=create_content_plan_number_menu(
                len(displayed_content_plans)
            ),
        )
        return

    selected_content_plan = content_plans[number - 1]

    await state.update_data(
        content_plan_number=number,
        selected_content_plan=selected_content_plan,
    )

    await state.set_state(
        EditContentPlan.waiting_for_client
    )

    await send_long_message(
        message,
        "✏️ Выбран контент-план:\n\n"
        f"{selected_content_plan}",
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

    if not content_plans:
        await state.clear()

        await message.answer(
            "📭 Сохранённых контент-планов больше нет.",
            reply_markup=content_plan_menu,
        )
        return

    await state.set_state(
        EditContentPlan.waiting_for_number
    )

    await show_content_plan_number_selection(
        message,
        state,
        content_plans,
        "Нажми номер плана, который нужно отредактировать.",
    )


@router.message(
    EditContentPlan.waiting_for_client
)
async def select_client_for_edit(
    message: Message,
    state: FSMContext,
):
    selected_text = (message.text or "").strip()
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

    await state.update_data(
        selected_ideas=[]
    )

    await state.set_state(
        EditContentPlan.waiting_for_ideas
    )

    await show_idea_selection(
        message,
        state,
        [],
    )


@router.message(
    EditContentPlan.waiting_for_ideas,
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
    EditContentPlan.waiting_for_ideas
)
async def select_ideas_for_edit(
    message: Message,
    state: FSMContext,
):
    selected_text = (message.text or "").strip()
    current_post_ideas = load_post_ideas()

    data = await state.get_data()
    post_ideas = data.get(
        "post_idea_choices",
        current_post_ideas,
    )
    selected_ideas = list(
        data.get("selected_ideas", [])
    )

    if selected_text == SKIP_IDEAS_BUTTON:
        await state.update_data(
            selected_ideas=[]
        )

        await state.set_state(
            EditContentPlan.waiting_for_new_brief
        )

        await ask_for_new_brief(message)
        return

    if selected_text == FINISH_IDEAS_BUTTON:
        missing_selected_ideas = [
            idea
            for idea in selected_ideas
            if idea not in current_post_ideas
        ]

        if missing_selected_ideas:
            selected_ideas = [
                idea
                for idea in selected_ideas
                if idea in current_post_ideas
            ]

            await state.update_data(
                selected_ideas=selected_ideas
            )

            await message.answer(
                "Список идей изменился. "
                "Выбери доступные идеи заново."
            )
            await show_idea_selection(
                message,
                state,
                selected_ideas,
                post_ideas=current_post_ideas,
            )
            return

        if not selected_ideas:
            await message.answer(
                "Сначала выбери хотя бы одну идею "
                "или нажми «Пропустить идеи».",
                reply_markup=create_ideas_menu(
                    post_ideas,
                    selected_ideas,
                ),
            )
            return

        await state.set_state(
            EditContentPlan.waiting_for_new_brief
        )

        await ask_for_new_brief(message)
        return

    selected_number = get_selected_idea_number(
        selected_text,
        len(post_ideas),
    )

    if selected_number is None:
        await message.answer(
            "Пожалуйста, выбери идею "
            "кнопкой ниже.",
            reply_markup=create_ideas_menu(
                post_ideas,
                selected_ideas,
            ),
        )
        return

    selected_idea = post_ideas[selected_number - 1]

    if selected_idea not in current_post_ideas:
        selected_ideas = [
            idea
            for idea in selected_ideas
            if idea in current_post_ideas
        ]

        await state.update_data(
            selected_ideas=selected_ideas
        )

        await message.answer(
            "Список идей изменился. "
            "Выбери идею в обновлённом списке."
        )
        await show_idea_selection(
            message,
            state,
            selected_ideas,
            post_ideas=current_post_ideas,
        )
        return

    if selected_idea in selected_ideas:
        selected_ideas.remove(selected_idea)
    else:
        selected_ideas.append(selected_idea)

    await state.update_data(
        selected_ideas=selected_ideas
    )

    await show_idea_selection(
        message,
        state,
        selected_ideas,
        show_full_list=False,
        post_ideas=post_ideas,
    )


@router.message(
    EditContentPlan.waiting_for_new_brief,
    F.text == BACK_BUTTON,
)
async def back_to_edit_idea_selection(
    message: Message,
    state: FSMContext,
):
    data = await state.get_data()

    selected_ideas = data.get(
        "selected_ideas",
        [],
    )

    await state.set_state(
        EditContentPlan.waiting_for_ideas
    )

    await show_idea_selection(
        message,
        state,
        selected_ideas,
    )


@router.message(
    EditContentPlan.waiting_for_new_brief
)
async def edit_content_plan(
    message: Message,
    state: FSMContext,
):
    new_brief = (message.text or "").strip()

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

    selected_content_plan = data.get(
        "selected_content_plan"
    )

    selected_client = data.get(
        "selected_client"
    )

    selected_ideas = data.get(
        "selected_ideas",
        [],
    )

    content_plans = read_content_plans()

    if (
        number is None
        or number < 1
        or number > len(content_plans)
        or content_plans[number - 1] != selected_content_plan
    ):
        await state.clear()

        await message.answer(
            "Выбранный контент-план "
            "больше не найден.",
            reply_markup=content_plan_menu,
        )
        return

    current_post_ideas = load_post_ideas()
    missing_selected_ideas = [
        idea
        for idea in selected_ideas
        if idea not in current_post_ideas
    ]

    if missing_selected_ideas:
        selected_ideas = [
            idea
            for idea in selected_ideas
            if idea in current_post_ideas
        ]

        await state.update_data(
            selected_ideas=selected_ideas
        )
        await state.set_state(
            EditContentPlan.waiting_for_ideas
        )

        await message.answer(
            "Список идей изменился. "
            "Выбери доступные идеи заново."
        )
        await show_idea_selection(
            message,
            state,
            selected_ideas,
            post_ideas=current_post_ideas,
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
                selected_ideas,
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

    latest_post_ideas = load_post_ideas()
    missing_selected_ideas = [
        idea
        for idea in selected_ideas
        if idea not in latest_post_ideas
    ]

    if missing_selected_ideas:
        selected_ideas = [
            idea
            for idea in selected_ideas
            if idea in latest_post_ideas
        ]

        await state.update_data(
            selected_ideas=selected_ideas
        )
        await state.set_state(
            EditContentPlan.waiting_for_ideas
        )

        await message.answer(
            "Список идей изменился во время обновления. "
            "Контент-план не сохранён; выбери идеи заново."
        )
        await show_idea_selection(
            message,
            state,
            selected_ideas,
            post_ideas=latest_post_ideas,
        )
        return

    current_content_plans = read_content_plans()

    if (
        number > len(current_content_plans)
        or current_content_plans[number - 1] != selected_content_plan
    ):
        await state.clear()

        await message.answer(
            "Список контент-планов изменился во время обновления. "
            "Ничего не сохранено; выбери план заново.",
            reply_markup=content_plan_menu,
        )
        return

    current_content_plans[number - 1] = (
        updated_content_plan
    )

    save_content_plans(current_content_plans)

    await state.clear()

    await send_long_message(
        message,
        "✅ Контент-план успешно обновлён:\n\n"
        f"{updated_content_plan}",
        reply_markup=content_plan_menu,
    )


@router.message(
    StateFilter(None),
    F.text == BACK_BUTTON,
)
async def back(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    await message.answer(
        "Главное меню:",
        reply_markup=main_menu,
    )
