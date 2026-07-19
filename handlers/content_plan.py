import asyncio

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)
from openai.types.responses import EasyInputMessageParam, ResponseInputParam
from openai.types.shared.reasoning_effort import ReasoningEffort
from openai.types.shared_params.reasoning import Reasoning
from pydantic import BaseModel, Field, ValidationError

from handlers.start import main_menu


router = Router()

CONTENT_PLANS_FILE = "content_plans.txt"
SEPARATOR = "-" * 40
OPENAI_MODEL = "gpt-5.6"
OPENAI_REASONING_EFFORT: ReasoningEffort = "low"
OPENAI_TIMEOUT_SECONDS = 45.0
MAX_BRIEF_LENGTH = 500

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
    days: list[ContentPlanDay] = Field(min_length=7, max_length=7)


class ContentPlanGenerationError(Exception):
    pass


class CreateContentPlan(StatesGroup):
    waiting_for_topic = State()


class SearchContentPlan(StatesGroup):
    waiting_for_query = State()


class DeleteContentPlan(StatesGroup):
    waiting_for_number = State()


class EditContentPlan(StatesGroup):
    waiting_for_number = State()
    waiting_for_new_topic = State()


content_plan_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Создать контент-план")],
        [KeyboardButton(text="📋 Мои контент-планы")],
        [KeyboardButton(text="🔍 Найти контент-план")],
        [KeyboardButton(text="✏️ Редактировать контент-план")],
        [KeyboardButton(text="🗑 Удалить контент-план")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True,
)


def read_content_plans():
    try:
        with open(CONTENT_PLANS_FILE, "r", encoding="utf-8") as file:
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
    with open(CONTENT_PLANS_FILE, "w", encoding="utf-8") as file:
        for content_plan in content_plans:
            file.write(content_plan.strip())
            file.write("\n")
            file.write(SEPARATOR)
            file.write("\n")


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
                content=f"Краткий бриф пользователя:\n{brief}",
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
    except (APITimeoutError, APIConnectionError) as error:
        raise ContentPlanGenerationError(
            "OpenAI сейчас не отвечает. "
            "Проверьте интернет-соединение и попробуйте ещё раз."
        ) from error
    except APIStatusError as error:
        raise ContentPlanGenerationError(
            "OpenAI вернул ошибку сервиса. "
            "Контент-план не сохранён; попробуйте позже."
        ) from error
    except OpenAIError as error:
        raise ContentPlanGenerationError(
            "Не удалось получить ответ OpenAI. "
            "Контент-план не сохранён; попробуйте позже."
        ) from error
    except (ValidationError, ValueError) as error:
        raise ContentPlanGenerationError(
            "OpenAI вернул неполный контент-план. "
            "Ничего не сохранено; попробуйте ещё раз."
        ) from error

    content_plan = response.output_parsed

    if content_plan is None:
        raise ContentPlanGenerationError(
            "OpenAI не сформировал контент-план. "
            "Ничего не сохранено; попробуйте ещё раз."
        )

    if [item.day for item in content_plan.days] != list(range(1, 8)):
        raise ContentPlanGenerationError(
            "OpenAI вернул дни в неверном порядке. "
            "Ничего не сохранено; попробуйте ещё раз."
        )

    return content_plan


def format_content_plan_text(brief, content_plan):
    result = (
        "📅 AI-контент-план на 7 дней\n\n"
        f"Бриф: {brief}\n\n"
    )

    for item in content_plan.days:
        result += (
            f"День {item.day}\n"
            f"🎯 Цель: {item.goal}\n"
            f"📝 Тема: {item.topic}\n"
            f"📌 Формат: {item.format}\n"
            f"💬 Ключевой тезис: {item.key_message}\n"
            f"👉 CTA: {item.cta}\n\n"
        )

    return result.strip()


async def build_content_plan_text(brief):
    content_plan = await asyncio.to_thread(
        generate_ai_content_plan,
        brief,
    )
    return format_content_plan_text(brief, content_plan)


def format_content_plans_list(content_plans):
    result = "📋 Мои контент-планы:\n\n"

    for index, content_plan in enumerate(content_plans, start=1):
        result += f"№ {index}\n{content_plan}\n\n"

    return result


@router.message(F.text == "📅 Контент-план")
async def open_content_plan_menu(message: Message):
    await message.answer(
        "📅 Раздел «Контент-план»\n\nВыбери действие:",
        reply_markup=content_plan_menu,
    )


@router.message(F.text == "📅 Создать контент-план")
async def ask_content_plan_topic(
    message: Message,
    state: FSMContext,
):
    await state.set_state(CreateContentPlan.waiting_for_topic)

    await message.answer(
        "Введите краткий бриф для контент-плана одним сообщением:\n\n"
        "• ниша или продукт;\n"
        "• целевая аудитория;\n"
        "• цель продвижения.\n\n"
        f"Максимум {MAX_BRIEF_LENGTH} символов."
    )


@router.message(CreateContentPlan.waiting_for_topic)
async def create_content_plan(
    message: Message,
    state: FSMContext,
):
    brief = message.text.strip()

    if not brief:
        await message.answer(
            "Бриф не может быть пустым. "
            "Введите данные для контент-плана:"
        )
        return

    if len(brief) > MAX_BRIEF_LENGTH:
        await message.answer(
            f"Бриф слишком длинный. "
            f"Сократите его до {MAX_BRIEF_LENGTH} символов:"
        )
        return

    await message.answer(
        "⏳ Создаю контент-план с помощью GPT-5.6..."
    )

    try:
        content_plan = await build_content_plan_text(brief)
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

    await message.answer(content_plan)
    await message.answer(
        "✅ Контент-план успешно сохранён.",
        reply_markup=content_plan_menu,
    )


@router.message(F.text == "📋 Мои контент-планы")
async def show_content_plans(message: Message):
    content_plans = read_content_plans()

    if not content_plans:
        await message.answer(
            "📭 У тебя пока нет сохранённых контент-планов."
        )
        return

    await message.answer(
        format_content_plans_list(content_plans)
    )


@router.message(F.text == "🔍 Найти контент-план")
async def ask_search_query(
    message: Message,
    state: FSMContext,
):
    await state.set_state(SearchContentPlan.waiting_for_query)

    await message.answer(
        "Введите слово или тему для поиска:"
    )


@router.message(SearchContentPlan.waiting_for_query)
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

    await message.answer(
        format_content_plans_list(found_content_plans),
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
            "📭 У тебя пока нет сохранённых контент-планов."
        )
        return

    await state.set_state(DeleteContentPlan.waiting_for_number)

    await message.answer(
        format_content_plans_list(content_plans)
        + "Введите номер контент-плана, который нужно удалить:"
    )


@router.message(DeleteContentPlan.waiting_for_number)
async def delete_content_plan(
    message: Message,
    state: FSMContext,
):
    content_plans = read_content_plans()

    if not message.text.isdigit():
        await message.answer(
            "Введите номер контент-плана цифрой:"
        )
        return

    number = int(message.text)

    if number < 1 or number > len(content_plans):
        await message.answer(
            "Контент-плана с таким номером нет. "
            "Введите корректный номер:"
        )
        return

    deleted_content_plan = content_plans.pop(number - 1)
    save_content_plans(content_plans)

    await state.clear()

    await message.answer(
        f"🗑 Контент-план удалён:\n\n{deleted_content_plan}",
        reply_markup=content_plan_menu,
    )


@router.message(F.text == "✏️ Редактировать контент-план")
async def ask_edit_content_plan_number(
    message: Message,
    state: FSMContext,
):
    content_plans = read_content_plans()

    if not content_plans:
        await message.answer(
            "📭 У тебя пока нет сохранённых контент-планов."
        )
        return

    await state.set_state(EditContentPlan.waiting_for_number)

    await message.answer(
        format_content_plans_list(content_plans)
        + "Введите номер контент-плана, который нужно отредактировать:"
    )


@router.message(EditContentPlan.waiting_for_number)
async def ask_new_content_plan_topic(
    message: Message,
    state: FSMContext,
):
    content_plans = read_content_plans()

    if not message.text.isdigit():
        await message.answer(
            "Введите номер контент-плана цифрой:"
        )
        return

    number = int(message.text)

    if number < 1 or number > len(content_plans):
        await message.answer(
            "Контент-плана с таким номером нет. "
            "Введите корректный номер:"
        )
        return

    await state.update_data(content_plan_number=number)
    await state.set_state(
        EditContentPlan.waiting_for_new_topic
    )

    await message.answer(
        "Введите новый краткий бриф для AI-контент-плана "
        f"(до {MAX_BRIEF_LENGTH} символов):"
    )


@router.message(EditContentPlan.waiting_for_new_topic)
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
            f"Бриф слишком длинный. "
            f"Сократите его до {MAX_BRIEF_LENGTH} символов:"
        )
        return

    data = await state.get_data()
    number = data["content_plan_number"]

    await message.answer(
        "⏳ Обновляю контент-план с помощью GPT-5.6..."
    )

    try:
        updated_content_plan = await build_content_plan_text(
            new_brief
        )
    except ContentPlanGenerationError as error:
        await state.clear()
        await message.answer(
            str(error),
            reply_markup=content_plan_menu,
        )
        return

    content_plans = read_content_plans()
    content_plans[number - 1] = updated_content_plan

    save_content_plans(content_plans)

    await state.clear()

    await message.answer(
        "✅ Контент-план успешно обновлён:\n\n"
        f"{content_plans[number - 1]}",
        reply_markup=content_plan_menu,
    )


@router.message(F.text == "⬅️ Назад")
async def back(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    await message.answer(
        "Главное меню:",
        reply_markup=main_menu,
    )