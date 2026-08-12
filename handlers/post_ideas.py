from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from handlers.start import main_menu
from services import post_ideas as post_ideas_service
from storage import post_ideas as post_ideas_storage

router = Router()


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
    return post_ideas_storage.load_post_ideas()


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

    idea = post_ideas_service.choose_random_post_idea(
        post_ideas
    )

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
    (
        creation_status,
        formatted_idea,
    ) = post_ideas_service.create_post_idea(
        message.text
    )

    if creation_status == post_ideas_service.IDEA_DUPLICATE:
        await state.clear()

        await message.answer(
            "⚠️ Такая идея уже есть в списке.",
            reply_markup=post_ideas_menu
        )
        return

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
    await state.update_data(
        post_ideas_snapshot=list(post_ideas)
    )

    await message.answer(
        format_post_ideas_list(post_ideas)
        + "\nВведите номер идеи, которую нужно удалить:"
    )


@router.message(DeletePostIdea.waiting_for_idea_number)
async def delete_post_idea_by_number(message: Message, state: FSMContext):
    data = await state.get_data()

    (
        deletion_status,
        deleted_idea,
        current_post_ideas,
    ) = post_ideas_service.delete_post_idea(
        message.text,
        data.get("post_ideas_snapshot"),
    )

    if deletion_status == post_ideas_service.IDEA_NUMBER_NOT_DIGIT:
        await message.answer("Введите номер идеи числом.")
        return

    if deletion_status == post_ideas_service.IDEA_NUMBER_NOT_FOUND:
        await message.answer("Идеи с таким номером нет.")
        return

    if deletion_status == post_ideas_service.IDEA_SELECTION_STALE:
        if not current_post_ideas:
            await state.clear()

            await message.answer(
                "Список идей пока пуст.",
                reply_markup=post_ideas_menu,
            )
            return

        await state.update_data(
            post_ideas_snapshot=list(current_post_ideas)
        )

        await message.answer(
            format_post_ideas_list(current_post_ideas)
            + "\nВведите номер идеи, которую нужно удалить:"
        )
        return

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
    found_ideas = post_ideas_service.find_post_ideas(
        post_ideas,
        message.text,
    )

    await state.clear()

    if not found_ideas:
        await message.answer(
            "По вашему запросу ничего не найдено.",
            reply_markup=post_ideas_menu
        )
        return

    await message.answer(
        "🔍 Найденные идеи:\n\n"
        + "\n".join(
            f"{number}. {idea}"
            for number, idea in found_ideas
        ),
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

    (
        selection_status,
        idea_number,
        selected_idea,
    ) = post_ideas_service.select_post_idea_by_number(
        post_ideas,
        message.text,
    )

    if selection_status == post_ideas_service.IDEA_NUMBER_NOT_DIGIT:
        await message.answer("Введите номер идеи числом.")
        return

    if selection_status == post_ideas_service.IDEA_NUMBER_NOT_FOUND:
        await message.answer("Идеи с таким номером нет.")
        return

    await state.update_data(
        idea_number=idea_number,
        selected_idea=selected_idea,
    )

    await state.set_state(EditPostIdea.waiting_for_new_idea_text)

    await message.answer(
        f"Текущая идея:\n\n{selected_idea}\n\n"
        "Введите новый текст идеи:"
    )


@router.message(EditPostIdea.waiting_for_new_idea_text)
async def save_edited_post_idea(message: Message, state: FSMContext):
    data = await state.get_data()
    idea_number = data.get("idea_number")
    selected_idea = data.get("selected_idea")

    (
        edit_status,
        formatted_idea,
        current_post_ideas,
    ) = post_ideas_service.edit_post_idea(
        idea_number,
        selected_idea,
        message.text,
    )

    if edit_status == post_ideas_service.IDEA_SELECTION_STALE:
        if not current_post_ideas:
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
            format_post_ideas_list(current_post_ideas)
            + "\nСписок идей изменился. "
            "Выберите номер идеи заново:"
        )
        return

    if edit_status == post_ideas_service.IDEA_DUPLICATE:
        await state.clear()

        await message.answer(
            "⚠️ Такая идея уже есть в списке.",
            reply_markup=post_ideas_menu
        )
        return

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
