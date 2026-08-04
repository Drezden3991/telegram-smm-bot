import random

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from handlers.start import main_menu

router = Router()

POST_IDEAS_FILE = "post_ideas.txt"


class AddPostIdea(StatesGroup):
    waiting_for_idea = State()


class DeletePostIdea(StatesGroup):
    waiting_for_idea_number = State()


class SearchPostIdea(StatesGroup):
    waiting_for_search_text = State()


class EditPostIdea(StatesGroup):
    waiting_for_idea_number = State()
    waiting_for_new_idea_text = State()


post_ideas_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💡 Получить идею")],
        [KeyboardButton(text="📋 Все идеи")],
        [KeyboardButton(text="➕ Добавить идею")],
        [KeyboardButton(text="🗑 Удалить идею")],
        [KeyboardButton(text="🔍 Найти идею")],
        [KeyboardButton(text="✏️ Редактировать идею")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True,
)


def load_post_ideas():
    try:
        with open(POST_IDEAS_FILE, "r", encoding="utf-8") as file:
            return [line.strip() for line in file.readlines() if line.strip()]
    except FileNotFoundError:
        return []


def save_all_post_ideas(post_ideas):
    with open(POST_IDEAS_FILE, "w", encoding="utf-8") as file:
        for idea in post_ideas:
            file.write(format_post_idea(idea) + "\n")


def format_post_idea(idea):
    idea = idea.strip()

    if not idea.startswith("💡"):
        idea = "💡 " + idea

    return idea


def normalize_post_idea(idea):
    idea = idea.strip().lower()

    if idea.startswith("💡"):
        idea = idea[1:].strip()

    return idea


def post_idea_exists(new_idea):
    post_ideas = load_post_ideas()
    new_idea = normalize_post_idea(new_idea)

    for idea in post_ideas:
        if normalize_post_idea(idea) == new_idea:
            return True

    return False


def add_post_idea_to_file(idea):
    idea = format_post_idea(idea)

    with open(POST_IDEAS_FILE, "a+", encoding="utf-8") as file:
        file.seek(0, 2)

        if file.tell() > 0:
            file.seek(file.tell() - 1)
            last_symbol = file.read(1)

            if last_symbol != "\n":
                file.write("\n")

        file.write(idea + "\n")


def format_post_ideas_list(post_ideas):
    text = "📋 Список идей:\n\n"

    for number, idea in enumerate(post_ideas, start=1):
        text += f"{number}. {idea}\n"

    return text


@router.message(
    StateFilter(
        AddPostIdea.waiting_for_idea,
        DeletePostIdea.waiting_for_idea_number,
        SearchPostIdea.waiting_for_search_text,
        EditPostIdea.waiting_for_idea_number,
    ),
    F.text == "⬅️ Назад",
)
async def cancel_post_idea_action(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    await message.answer(
        "💡 Раздел «Идея постов»\n\nВыбери действие:",
        reply_markup=post_ideas_menu,
    )


@router.message(
    EditPostIdea.waiting_for_new_idea_text,
    F.text == "⬅️ Назад",
)
async def back_to_post_idea_number(
    message: Message,
    state: FSMContext,
):
    post_ideas = load_post_ideas()

    if not post_ideas:
        await state.clear()

        await message.answer(
            "Список идей пока пуст.",
            reply_markup=post_ideas_menu,
        )
        return

    await state.set_state(
        EditPostIdea.waiting_for_idea_number
    )

    await message.answer(
        format_post_ideas_list(post_ideas)
        + "\nВведите номер идеи, которую нужно отредактировать:"
    )


@router.message(F.text == "💡 Идея постов")
async def open_post_ideas_menu(message: Message):
    await message.answer(
        "💡 Раздел «Идея постов»\n\nВыбери действие:",
        reply_markup=post_ideas_menu
    )


@router.message(F.text == "💡 Получить идею")
async def random_post_idea(message: Message):
    post_ideas = load_post_ideas()

    if not post_ideas:
        await message.answer("Список идей пока пуст.")
        return

    idea = random.choice(post_ideas)

    await message.answer(idea)


@router.message(F.text == "📋 Все идеи")
async def show_all_post_ideas(message: Message):
    post_ideas = load_post_ideas()

    if not post_ideas:
        await message.answer("Список идей пока пуст.")
        return

    await message.answer(format_post_ideas_list(post_ideas))


@router.message(F.text == "➕ Добавить идею")
async def add_post_idea(message: Message, state: FSMContext):
    await state.set_state(AddPostIdea.waiting_for_idea)

    await message.answer("Введите новую идею поста:")


@router.message(AddPostIdea.waiting_for_idea)
async def save_new_post_idea(message: Message, state: FSMContext):
    idea = message.text

    if post_idea_exists(idea):
        await state.clear()

        await message.answer(
            "⚠️ Такая идея уже есть в списке.",
            reply_markup=post_ideas_menu
        )
        return

    formatted_idea = format_post_idea(idea)

    add_post_idea_to_file(formatted_idea)

    await state.clear()

    await message.answer(
        f"✅ Идея добавлена:\n\n{formatted_idea}",
        reply_markup=post_ideas_menu
    )


@router.message(F.text == "🗑 Удалить идею")
async def delete_post_idea(message: Message, state: FSMContext):
    post_ideas = load_post_ideas()

    if not post_ideas:
        await message.answer("Список идей пока пуст.")
        return

    await state.set_state(DeletePostIdea.waiting_for_idea_number)

    await message.answer(
        format_post_ideas_list(post_ideas)
        + "\nВведите номер идеи, которую нужно удалить:"
    )


@router.message(DeletePostIdea.waiting_for_idea_number)
async def delete_post_idea_by_number(message: Message, state: FSMContext):
    post_ideas = load_post_ideas()

    if not message.text.isdigit():
        await message.answer("Введите номер идеи числом.")
        return

    idea_number = int(message.text)

    if idea_number < 1 or idea_number > len(post_ideas):
        await message.answer("Идеи с таким номером нет.")
        return

    deleted_idea = post_ideas.pop(idea_number - 1)

    save_all_post_ideas(post_ideas)

    await state.clear()

    await message.answer(
        f"🗑 Идея удалена:\n\n{deleted_idea}",
        reply_markup=post_ideas_menu
    )


@router.message(F.text == "🔍 Найти идею")
async def search_post_idea(message: Message, state: FSMContext):
    post_ideas = load_post_ideas()

    if not post_ideas:
        await message.answer("Список идей пока пуст.")
        return

    await state.set_state(SearchPostIdea.waiting_for_search_text)

    await message.answer("Введите слово или фразу для поиска:")


@router.message(SearchPostIdea.waiting_for_search_text)
async def show_found_post_ideas(message: Message, state: FSMContext):
    post_ideas = load_post_ideas()
    search_text = message.text.lower().strip()

    found_ideas = []

    for number, idea in enumerate(post_ideas, start=1):
        if search_text in idea.lower():
            found_ideas.append(f"{number}. {idea}")

    await state.clear()

    if not found_ideas:
        await message.answer(
            "По вашему запросу ничего не найдено.",
            reply_markup=post_ideas_menu
        )
        return

    await message.answer(
        "🔍 Найденные идеи:\n\n" + "\n".join(found_ideas),
        reply_markup=post_ideas_menu
    )


@router.message(F.text == "✏️ Редактировать идею")
async def edit_post_idea(message: Message, state: FSMContext):
    post_ideas = load_post_ideas()

    if not post_ideas:
        await message.answer("Список идей пока пуст.")
        return

    await state.set_state(EditPostIdea.waiting_for_idea_number)

    await message.answer(
        format_post_ideas_list(post_ideas)
        + "\nВведите номер идеи, которую нужно отредактировать:"
    )


@router.message(EditPostIdea.waiting_for_idea_number)
async def choose_post_idea_for_edit(message: Message, state: FSMContext):
    post_ideas = load_post_ideas()

    if not message.text.isdigit():
        await message.answer("Введите номер идеи числом.")
        return

    idea_number = int(message.text)

    if idea_number < 1 or idea_number > len(post_ideas):
        await message.answer("Идеи с таким номером нет.")
        return

    await state.update_data(
        idea_number=idea_number,
        selected_idea=post_ideas[idea_number - 1],
    )

    await state.set_state(EditPostIdea.waiting_for_new_idea_text)

    await message.answer(
        f"Текущая идея:\n\n{post_ideas[idea_number - 1]}\n\n"
        "Введите новый текст идеи:"
    )


@router.message(EditPostIdea.waiting_for_new_idea_text)
async def save_edited_post_idea(message: Message, state: FSMContext):
    post_ideas = load_post_ideas()
    data = await state.get_data()
    idea_number = data.get("idea_number")
    selected_idea = data.get("selected_idea")

    if (
        not isinstance(idea_number, int)
        or idea_number < 1
        or idea_number > len(post_ideas)
        or post_ideas[idea_number - 1] != selected_idea
    ):
        if not post_ideas:
            await state.clear()

            await message.answer(
                "Список идей изменился, и сохранённых идей больше нет.",
                reply_markup=post_ideas_menu,
            )
            return

        await state.set_state(
            EditPostIdea.waiting_for_idea_number
        )

        await message.answer(
            format_post_ideas_list(post_ideas)
            + "\nСписок идей изменился. "
            "Выберите номер идеи заново:"
        )
        return

    new_idea = message.text

    old_idea = post_ideas[idea_number - 1]
    post_ideas.pop(idea_number - 1)

    if post_idea_exists(new_idea):
        post_ideas.insert(idea_number - 1, old_idea)
        save_all_post_ideas(post_ideas)

        await state.clear()

        await message.answer(
            "⚠️ Такая идея уже есть в списке.",
            reply_markup=post_ideas_menu
        )
        return

    formatted_idea = format_post_idea(new_idea)
    post_ideas.insert(idea_number - 1, formatted_idea)

    save_all_post_ideas(post_ideas)

    await state.clear()

    await message.answer(
        f"✅ Идея обновлена:\n\n{formatted_idea}",
        reply_markup=post_ideas_menu
    )


@router.message(
    StateFilter(None),
    F.text == "⬅️ Назад",
)
async def back(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "Главное меню:",
        reply_markup=main_menu
    )
