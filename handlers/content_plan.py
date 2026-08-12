from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from handlers.start import main_menu
from services import content_plan as content_plan_service
from storage import clients as clients_storage
from storage import content_plans as content_plans_storage
from storage import post_ideas as post_ideas_storage


router = Router()

MAX_BRIEF_LENGTH = 500
TELEGRAM_MESSAGE_LIMIT = 4096
ContentPlanGenerationError = (
    content_plan_service.ContentPlanGenerationError
)

WITHOUT_CLIENT_BUTTON = "🚫 Без клиента"
SKIP_IDEAS_BUTTON = "⏭ Пропустить идеи"
FINISH_IDEAS_BUTTON = "✅ Готово"
BACK_BUTTON = "⬅️ Назад"
CONFIRM_DELETE_BUTTON = "✅ Да, удалить"
CANCEL_DELETE_BUTTON = "❌ Отмена"

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
    return content_plans_storage.read_content_plans()


def load_clients():
    return clients_storage.load_clients()


def load_post_ideas():
    return post_ideas_storage.load_post_ideas()


def get_client_full_name(client):
    return content_plan_service.get_client_full_name(
        client
    )


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
    return content_plan_service.get_selected_client(
        message_text,
        clients,
    )


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
    return content_plan_service.get_selected_idea_number(
        message_text,
        ideas_count,
    )


def format_numbered_ideas(post_ideas):
    return content_plan_service.format_numbered_ideas(
        post_ideas
    )


def format_selected_ideas(
    post_ideas,
    selected_ideas,
):
    return content_plan_service.format_selected_ideas(
        post_ideas,
        selected_ideas,
    )


async def build_content_plan_text(
    client,
    selected_ideas,
    user_brief,
):
    return await content_plan_service.build_content_plan_text(
        client,
        selected_ideas,
        user_brief,
    )


def format_content_plans_list(content_plans):
    return content_plan_service.format_content_plans_list(
        content_plans
    )


def format_compact_content_plans_list(content_plans):
    return content_plan_service.format_compact_content_plans_list(
        content_plans
    )


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
    return content_plan_service.get_selected_content_plan_number(
        message_text,
        content_plans_count,
    )


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
    (
        selected_ideas,
        _,
    ) = content_plan_service.reconcile_selected_ideas(
        selected_ideas,
        post_ideas,
    )

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
        (
            selected_ideas,
            missing_selected_ideas,
        ) = content_plan_service.reconcile_selected_ideas(
            selected_ideas,
            current_post_ideas,
        )

        if missing_selected_ideas:
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
        (
            selected_ideas,
            _,
        ) = content_plan_service.reconcile_selected_ideas(
            selected_ideas,
            current_post_ideas,
        )

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

    selected_ideas = content_plan_service.toggle_selected_idea(
        selected_ideas,
        selected_idea,
    )

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
    (
        selected_ideas,
        missing_selected_ideas,
    ) = content_plan_service.reconcile_selected_ideas(
        selected_ideas,
        current_post_ideas,
    )

    if missing_selected_ideas:
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
    (
        selected_ideas,
        missing_selected_ideas,
    ) = content_plan_service.reconcile_selected_ideas(
        selected_ideas,
        latest_post_ideas,
    )

    if missing_selected_ideas:
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

    content_plan_service.create_and_save_content_plan(
        content_plan
    )

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
    content_plans = read_content_plans()
    found_content_plans = content_plan_service.find_content_plans(
        content_plans,
        message.text or "",
    )

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
    (
        content_plan_was_deleted,
        deleted_content_plan,
        content_plans,
    ) = content_plan_service.delete_content_plan(
        number,
        selected_content_plan,
    )

    if not content_plan_was_deleted:
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
        (
            selected_ideas,
            missing_selected_ideas,
        ) = content_plan_service.reconcile_selected_ideas(
            selected_ideas,
            current_post_ideas,
        )

        if missing_selected_ideas:
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
        (
            selected_ideas,
            _,
        ) = content_plan_service.reconcile_selected_ideas(
            selected_ideas,
            current_post_ideas,
        )

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

    selected_ideas = content_plan_service.toggle_selected_idea(
        selected_ideas,
        selected_idea,
    )

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

    if not content_plan_service.is_current_content_plan_selection(
        content_plans,
        number,
        selected_content_plan,
    ):
        await state.clear()

        await message.answer(
            "Выбранный контент-план "
            "больше не найден.",
            reply_markup=content_plan_menu,
        )
        return

    current_post_ideas = load_post_ideas()
    (
        selected_ideas,
        missing_selected_ideas,
    ) = content_plan_service.reconcile_selected_ideas(
        selected_ideas,
        current_post_ideas,
    )

    if missing_selected_ideas:
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
    (
        selected_ideas,
        missing_selected_ideas,
    ) = content_plan_service.reconcile_selected_ideas(
        selected_ideas,
        latest_post_ideas,
    )

    if missing_selected_ideas:
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

    (
        content_plan_was_replaced,
        _,
    ) = content_plan_service.replace_content_plan(
        number,
        selected_content_plan,
        updated_content_plan,
    )

    if not content_plan_was_replaced:
        await state.clear()

        await message.answer(
            "Список контент-планов изменился во время обновления. "
            "Ничего не сохранено; выбери план заново.",
            reply_markup=content_plan_menu,
        )
        return

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
