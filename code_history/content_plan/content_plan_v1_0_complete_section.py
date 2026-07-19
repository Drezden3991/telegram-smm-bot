from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from handlers.start import main_menu


router = Router()

CONTENT_PLANS_FILE = "content_plans.txt"
SEPARATOR = "-" * 40


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


def create_content_plan_text(topic):
    return (
        "📅 Контент-план\n\n"
        f"Тема: {topic}\n\n"
        "1. Знакомство с темой.\n"
        "2. Главная проблема аудитории.\n"
        "3. Полезный совет по теме.\n"
        "4. Ошибка, которую часто допускают.\n"
        "5. Призыв к действию."
    )


def format_content_plans_list(content_plans):
    result = "📋 Мои контент-планы:\n\n"

    for index, content_plan in enumerate(content_plans, start=1):
        result += f"№ {index}\n{content_plan}\n\n"

    return result


@router.message(F.text == "📅 Контент-план")
async def open_content_plan_menu(message: Message):
    await message.answer(
        "📅 Раздел «Контент-план»\n\nВыбери действие:",
        reply_markup=content_plan_menu
    )


@router.message(F.text == "📅 Создать контент-план")
async def ask_content_plan_topic(message: Message, state: FSMContext):
    await state.set_state(CreateContentPlan.waiting_for_topic)

    await message.answer(
        "Введите тему для контент-плана:"
    )


@router.message(CreateContentPlan.waiting_for_topic)
async def create_content_plan(message: Message, state: FSMContext):
    topic = message.text.strip()

    if not topic:
        await message.answer(
            "Тема не может быть пустой. Введите тему для контент-плана:"
        )
        return

    content_plan = create_content_plan_text(topic)

    content_plans = read_content_plans()
    content_plans.append(content_plan)
    save_content_plans(content_plans)

    await state.clear()

    await message.answer(content_plan)
    await message.answer(
        "✅ Контент-план успешно сохранён.",
        reply_markup=content_plan_menu
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
async def ask_search_query(message: Message, state: FSMContext):
    await state.set_state(SearchContentPlan.waiting_for_query)

    await message.answer(
        "Введите слово или тему для поиска:"
    )


@router.message(SearchContentPlan.waiting_for_query)
async def search_content_plan(message: Message, state: FSMContext):
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
            reply_markup=content_plan_menu
        )
        return

    await message.answer(
        format_content_plans_list(found_content_plans),
        reply_markup=content_plan_menu
    )


@router.message(F.text == "🗑 Удалить контент-план")
async def ask_delete_content_plan_number(message: Message, state: FSMContext):
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
async def delete_content_plan(message: Message, state: FSMContext):
    content_plans = read_content_plans()

    if not message.text.isdigit():
        await message.answer(
            "Введите номер контент-плана цифрой:"
        )
        return

    number = int(message.text)

    if number < 1 or number > len(content_plans):
        await message.answer(
            "Контент-плана с таким номером нет. Введите корректный номер:"
        )
        return

    deleted_content_plan = content_plans.pop(number - 1)
    save_content_plans(content_plans)

    await state.clear()

    await message.answer(
        f"🗑 Контент-план удалён:\n\n{deleted_content_plan}",
        reply_markup=content_plan_menu
    )


@router.message(F.text == "✏️ Редактировать контент-план")
async def ask_edit_content_plan_number(message: Message, state: FSMContext):
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
async def ask_new_content_plan_topic(message: Message, state: FSMContext):
    content_plans = read_content_plans()

    if not message.text.isdigit():
        await message.answer(
            "Введите номер контент-плана цифрой:"
        )
        return

    number = int(message.text)

    if number < 1 or number > len(content_plans):
        await message.answer(
            "Контент-плана с таким номером нет. Введите корректный номер:"
        )
        return

    await state.update_data(content_plan_number=number)
    await state.set_state(EditContentPlan.waiting_for_new_topic)

    await message.answer(
        "Введите новую тему для контент-плана:"
    )


@router.message(EditContentPlan.waiting_for_new_topic)
async def edit_content_plan(message: Message, state: FSMContext):
    new_topic = message.text.strip()

    if not new_topic:
        await message.answer(
            "Тема не может быть пустой. Введите новую тему:"
        )
        return

    data = await state.get_data()
    number = data["content_plan_number"]

    content_plans = read_content_plans()
    content_plans[number - 1] = create_content_plan_text(new_topic)

    save_content_plans(content_plans)

    await state.clear()

    await message.answer(
        "✅ Контент-план успешно обновлён:\n\n"
        f"{content_plans[number - 1]}",
        reply_markup=content_plan_menu
    )


@router.message(F.text == "⬅️ Назад")
async def back(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "Главное меню:",
        reply_markup=main_menu
    )