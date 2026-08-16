from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from handlers.start import main_menu
from services import post_ideas as post_ideas_service
from storage import clients as clients_storage
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


class GeneratePostIdeas(StatesGroup):
    waiting_for_client = State()
    waiting_for_brief = State()
    waiting_for_provider = State()
    waiting_for_candidates = State()


BACK_BUTTON = "⬅️ Назад"
WITHOUT_CLIENT_BUTTON = "🚫 Без клиента"
SAVE_SELECTED_IDEAS_BUTTON = "✅ Сохранить выбранные"
OPENAI_PROVIDER_BUTTON = "OpenAI"
GEMINI_PROVIDER_BUTTON = "Gemini"
GROQ_PROVIDER_BUTTON = "Groq"


post_ideas_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💡 Получить идею")],
        [KeyboardButton(text="📋 Все идеи")],
        [KeyboardButton(text="➕ Добавить идею")],
        [KeyboardButton(text="🗑 Удалить идею")],
        [KeyboardButton(text="🔍 Найти идею")],
        [KeyboardButton(text="✏️ Редактировать идею")],
        [KeyboardButton(text="✨ Сгенерировать идеи")],
        [KeyboardButton(text=BACK_BUTTON)],
    ],
    resize_keyboard=True,
)


def load_post_ideas(telegram_user_id=None):
    return post_ideas_storage.load_post_ideas(telegram_user_id)


def load_clients(telegram_user_id=None):
    return clients_storage.load_clients(telegram_user_id)


def get_client_full_name(client):
    return post_ideas_service.get_client_full_name(client)


def create_ai_clients_menu(clients):
    keyboard = [
        [
            KeyboardButton(
                text=f"{number}. {get_client_full_name(client)}"
            )
        ]
        for number, client in enumerate(clients, start=1)
    ]
    keyboard.append([KeyboardButton(text=WITHOUT_CLIENT_BUTTON)])
    keyboard.append([KeyboardButton(text=BACK_BUTTON)])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
    )


def create_ai_provider_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=OPENAI_PROVIDER_BUTTON),
                KeyboardButton(text=GEMINI_PROVIDER_BUTTON),
                KeyboardButton(text=GROQ_PROVIDER_BUTTON),
            ],
            [KeyboardButton(text=BACK_BUTTON)],
        ],
        resize_keyboard=True,
    )


def get_selected_ai_provider(message_text):
    providers = {
        OPENAI_PROVIDER_BUTTON: "openai",
        GEMINI_PROVIDER_BUTTON: "gemini",
        GROQ_PROVIDER_BUTTON: "groq",
    }

    return providers.get(message_text)


def create_ai_candidates_menu(candidates, selected_candidates):
    keyboard = []

    for number, candidate in enumerate(candidates, start=1):
        prefix = "✅ " if candidate in selected_candidates else ""
        keyboard.append(
            [KeyboardButton(text=f"{prefix}{number}. {candidate}")]
        )

    keyboard.append([KeyboardButton(text=SAVE_SELECTED_IDEAS_BUTTON)])
    keyboard.append([KeyboardButton(text=BACK_BUTTON)])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
    )


def get_selected_ai_candidate(message_text, candidates):
    clean_text = message_text.removeprefix("✅ ")

    for number, candidate in enumerate(candidates, start=1):
        if clean_text == f"{number}. {candidate}":
            return candidate

    return None


async def show_ai_client_selection(message):
    clients = load_clients(message.from_user.id)

    await message.answer(
        "Выбери клиента для генерации идей "
        "или создай идеи без клиента:",
        reply_markup=create_ai_clients_menu(clients),
    )


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
    post_ideas = load_post_ideas(message.from_user.id)

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
    post_ideas = load_post_ideas(message.from_user.id)

    if not post_ideas:
        await message.answer("Список идей пока пуст.")
        return

    idea = post_ideas_service.choose_random_post_idea(
        post_ideas
    )
    await message.answer(idea)


@router.message(F.text == "✨ Сгенерировать идеи")
async def start_ai_post_ideas(
    message: Message,
    state: FSMContext,
):
    await state.clear()
    await state.set_state(GeneratePostIdeas.waiting_for_client)
    await show_ai_client_selection(message)


@router.message(
    GeneratePostIdeas.waiting_for_client,
    F.text == BACK_BUTTON,
)
async def cancel_ai_client_selection(
    message: Message,
    state: FSMContext,
):
    await state.clear()
    await message.answer(
        "💡 Раздел «Идея постов»\n\nВыбери действие:",
        reply_markup=post_ideas_menu,
    )


@router.message(GeneratePostIdeas.waiting_for_client)
async def select_ai_client(
    message: Message,
    state: FSMContext,
):
    clients = load_clients(message.from_user.id)
    selected_text = message.text.strip()

    if selected_text == WITHOUT_CLIENT_BUTTON:
        selected_client = None
    else:
        selected_client = None

        for number, client in enumerate(clients, start=1):
            if selected_text == f"{number}. {get_client_full_name(client)}":
                selected_client = client
                break

        if selected_client is None:
            await message.answer(
                "Пожалуйста, выбери клиента кнопкой ниже.",
                reply_markup=create_ai_clients_menu(clients),
            )
            return

    await state.update_data(selected_client=selected_client)
    await state.set_state(GeneratePostIdeas.waiting_for_brief)
    await message.answer(
        "Опиши, какие идеи нужны: тема, цель или задача.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=BACK_BUTTON)]],
            resize_keyboard=True,
        ),
    )


@router.message(
    GeneratePostIdeas.waiting_for_brief,
    F.text == BACK_BUTTON,
)
async def back_to_ai_client_selection(
    message: Message,
    state: FSMContext,
):
    await state.set_state(GeneratePostIdeas.waiting_for_client)
    await show_ai_client_selection(message)


@router.message(GeneratePostIdeas.waiting_for_brief)
async def get_ai_post_ideas_brief(
    message: Message,
    state: FSMContext,
):
    brief = message.text.strip()

    if not brief:
        await message.answer(
            "Описание не может быть пустым. Напиши, какие идеи нужны:"
        )
        return

    await state.update_data(ai_brief=brief)
    await state.set_state(GeneratePostIdeas.waiting_for_provider)
    await message.answer(
        "Выбери AI для генерации идей:",
        reply_markup=create_ai_provider_menu(),
    )


@router.message(
    GeneratePostIdeas.waiting_for_provider,
    F.text == BACK_BUTTON,
)
async def back_to_ai_brief(
    message: Message,
    state: FSMContext,
):
    await state.set_state(GeneratePostIdeas.waiting_for_brief)
    await message.answer(
        "Опиши, какие идеи нужны: тема, цель или задача.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=BACK_BUTTON)]],
            resize_keyboard=True,
        ),
    )


@router.message(GeneratePostIdeas.waiting_for_provider)
async def generate_ai_post_ideas(
    message: Message,
    state: FSMContext,
):
    provider = get_selected_ai_provider(message.text)

    if provider is None:
        await message.answer(
            "Пожалуйста, выбери AI кнопкой ниже.",
            reply_markup=create_ai_provider_menu(),
        )
        return

    data = await state.get_data()
    brief = data.get("ai_brief", "")

    if not brief:
        await state.set_state(GeneratePostIdeas.waiting_for_brief)
        await message.answer(
            "Описание не найдено. Напиши, какие идеи нужны:"
        )
        return

    await state.update_data(ai_provider=provider)
    await message.answer(
        f"⏳ Генерирую идеи через {message.text}..."
    )

    try:
        generation_args = (
            data.get("selected_client"), brief, provider
        )
        if message.from_user.id is not None:
            generation_args += (message.from_user.id,)
        candidates = post_ideas_service.generate_post_idea_candidates(
            *generation_args
        )
    except post_ideas_service.PostIdeasGenerationError as error:
        await state.clear()
        await message.answer(
            str(error),
            reply_markup=post_ideas_menu,
        )
        return

    await state.update_data(
        ai_candidates=list(candidates),
        selected_ai_candidates=[],
    )
    await state.set_state(GeneratePostIdeas.waiting_for_candidates)
    await message.answer(
        "Выбери идеи для сохранения, затем нажми «Сохранить выбранные».",
        reply_markup=create_ai_candidates_menu(candidates, []),
    )


@router.message(
    GeneratePostIdeas.waiting_for_candidates,
    F.text == BACK_BUTTON,
)
async def back_to_ai_provider_selection(
    message: Message,
    state: FSMContext,
):
    await state.set_state(GeneratePostIdeas.waiting_for_provider)
    await message.answer(
        "Выбери AI для генерации идей:",
        reply_markup=create_ai_provider_menu(),
    )


@router.message(
    GeneratePostIdeas.waiting_for_candidates,
    F.text == SAVE_SELECTED_IDEAS_BUTTON,
)
async def save_selected_ai_post_ideas(
    message: Message,
    state: FSMContext,
):
    data = await state.get_data()
    selected_ideas = data.get("selected_ai_candidates", [])

    if not selected_ideas:
        await message.answer(
            "Выбери хотя бы одну идею для сохранения.",
            reply_markup=create_ai_candidates_menu(
                data.get("ai_candidates", []),
                selected_ideas,
            ),
        )
        return

    save_args = (selected_ideas,)
    if message.from_user.id is not None:
        save_args += (message.from_user.id,)
    added_ideas, duplicate_ideas = (
        post_ideas_service.save_selected_post_ideas(*save_args)
    )
    await state.clear()

    if added_ideas:
        result = "✅ Идеи сохранены:\n\n" + "\n".join(added_ideas)

        if duplicate_ideas:
            result += "\n\n⚠️ Уже были в списке:\n" + "\n".join(
                duplicate_ideas
            )
    else:
        result = "⚠️ Все выбранные идеи уже есть в списке."

    await message.answer(result, reply_markup=post_ideas_menu)


@router.message(GeneratePostIdeas.waiting_for_candidates)
async def toggle_ai_post_idea_candidate(
    message: Message,
    state: FSMContext,
):
    data = await state.get_data()
    candidates = data.get("ai_candidates", [])
    selected_ideas = list(data.get("selected_ai_candidates", []))
    candidate = get_selected_ai_candidate(message.text, candidates)

    if candidate is None:
        await message.answer(
            "Пожалуйста, выбери идею кнопкой ниже.",
            reply_markup=create_ai_candidates_menu(
                candidates,
                selected_ideas,
            ),
        )
        return

    if candidate in selected_ideas:
        selected_ideas.remove(candidate)
    else:
        selected_ideas.append(candidate)

    await state.update_data(selected_ai_candidates=selected_ideas)
    await message.answer(
        "Выбери идеи для сохранения, затем нажми «Сохранить выбранные».",
        reply_markup=create_ai_candidates_menu(
            candidates,
            selected_ideas,
        ),
    )


@router.message(F.text == "📋 Все идеи")
async def show_all_post_ideas(message: Message):
    post_ideas = load_post_ideas(message.from_user.id)

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
        message.text,
        message.from_user.id,
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
    post_ideas = load_post_ideas(message.from_user.id)

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

    deletion_args = (message.text, data.get("post_ideas_snapshot"))
    if message.from_user.id is not None:
        deletion_args += (message.from_user.id,)
    (
        deletion_status,
        deleted_idea,
        current_post_ideas,
    ) = post_ideas_service.delete_post_idea(*deletion_args)

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
    post_ideas = load_post_ideas(message.from_user.id)

    if not post_ideas:
        await message.answer("Список идей пока пуст.")
        return

    await state.set_state(SearchPostIdea.waiting_for_search_text)

    await message.answer("Введите слово или фразу для поиска:")


@router.message(SearchPostIdea.waiting_for_search_text)
async def show_found_post_ideas(message: Message, state: FSMContext):
    post_ideas = load_post_ideas(message.from_user.id)
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
    post_ideas = load_post_ideas(message.from_user.id)

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
    post_ideas = load_post_ideas(message.from_user.id)

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

    edit_args = (
        idea_number,
        selected_idea,
        message.text,
    )
    if message.from_user.id is not None:
        edit_args += (message.from_user.id,)

    (
        edit_status,
        formatted_idea,
        current_post_ideas,
    ) = post_ideas_service.edit_post_idea(*edit_args)

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
