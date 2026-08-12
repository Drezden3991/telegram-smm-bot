import random

from models.client import Client
from storage import post_ideas as post_ideas_storage


IDEA_OPERATION_READY = "ready"
IDEA_NUMBER_NOT_DIGIT = "number_not_digit"
IDEA_NUMBER_NOT_FOUND = "number_not_found"
IDEA_DUPLICATE = "duplicate"
IDEA_SELECTION_STALE = "selection_stale"


class PostIdeasGenerationError(Exception):
    pass


POST_IDEAS_AI_CONTRACT = (
    "Ты помогаешь SMM-специалисту придумывать идеи публикаций. Верни "
    "ровно три разные самостоятельные и понятные идеи постов на русском "
    "языке. Учитывай безопасный контекст клиента, пользовательский бриф "
    "и существующие идеи. Не повторяй существующие идеи и не создавай "
    "очевидные смысловые дубли между тремя новыми кандидатами. Каждая "
    "идея должна быть короткой темой или замыслом публикации, а не готовым "
    "длинным текстом поста.\n\n"
    "ПОДТВЕРЖДЁННЫЕ ФАКТЫ О КЛИЕНТЕ — это только сведения, явно "
    "указанные во входном контексте. Не выдумывай и не приписывай клиенту "
    "цены, скидки, акции, промокоды, адреса, контакты, часы работы, товары, "
    "услуги, инфраструктуру, отзывы, награды, сертификаты, статистику и "
    "другие конкретные бизнес-факты, если их нет во входных данных.\n\n"
    "ОБЩИЕ ЗНАНИЯ допустимы только как нейтральная основа идеи; не "
    "превращай их в утверждения о конкретном клиенте. Если информации мало, "
    "делай идеи более общими, а не достраивай детали. Не добавляй объяснения, "
    "рассуждения, категории или оценки."
)


def get_client_full_name(client: Client) -> str:
    name = client.get("name", "").strip()
    last_name = client.get("last_name", "").strip()

    return f"{name} {last_name}".strip()


def build_client_ai_context(client: Client | None) -> str:
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

    return "\n".join(context_parts)


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


def post_idea_exists(new_idea, post_ideas):
    normalized_new_idea = normalize_post_idea(new_idea)

    for idea in post_ideas:
        if normalize_post_idea(idea) == normalized_new_idea:
            return True

    return False


def find_post_ideas(post_ideas, search_text):
    normalized_search_text = search_text.lower().strip()

    return [
        (number, idea)
        for number, idea in enumerate(post_ideas, start=1)
        if normalized_search_text in idea.lower()
    ]


def format_existing_post_ideas(existing_ideas: list[str]) -> str:
    if not existing_ideas:
        return "Нет."

    return "\n".join(
        f"{number}. {idea}"
        for number, idea in enumerate(
            existing_ideas,
            start=1,
        )
    )


def choose_random_post_idea(post_ideas):
    return random.choice(post_ideas)


def select_post_idea_by_number(post_ideas, number_text):
    if not number_text.isdigit():
        return IDEA_NUMBER_NOT_DIGIT, None, None

    idea_number = int(number_text)

    if idea_number < 1 or idea_number > len(post_ideas):
        return IDEA_NUMBER_NOT_FOUND, None, None

    return (
        IDEA_OPERATION_READY,
        idea_number,
        post_ideas[idea_number - 1],
    )


def prepare_post_idea_deletion(post_ideas, number_text):
    status, idea_number, selected_idea = select_post_idea_by_number(
        post_ideas,
        number_text,
    )

    if status != IDEA_OPERATION_READY:
        return status, None, None

    remaining_post_ideas = list(post_ideas)
    remaining_post_ideas.pop(idea_number - 1)

    return status, selected_idea, remaining_post_ideas


def is_current_post_idea_selection(
    post_ideas,
    idea_number,
    selected_idea,
):
    return (
        isinstance(idea_number, int)
        and idea_number >= 1
        and idea_number <= len(post_ideas)
        and post_ideas[idea_number - 1] == selected_idea
    )


def prepare_post_idea_edit(
    post_ideas,
    idea_number,
    new_idea,
    duplicate_exists,
):
    updated_post_ideas = list(post_ideas)
    old_idea = updated_post_ideas[idea_number - 1]

    if duplicate_exists:
        return IDEA_DUPLICATE, old_idea, updated_post_ideas

    formatted_idea = format_post_idea(new_idea)
    updated_post_ideas[idea_number - 1] = formatted_idea

    return IDEA_OPERATION_READY, formatted_idea, updated_post_ideas


def create_post_idea(idea):
    post_ideas = post_ideas_storage.load_post_ideas()

    if post_idea_exists(idea, post_ideas):
        return IDEA_DUPLICATE, None

    formatted_idea = format_post_idea(idea)
    post_ideas_storage.add_post_idea_to_file(
        formatted_idea
    )

    return IDEA_OPERATION_READY, formatted_idea


def generate_post_idea_candidates(
    client: Client | None,
    brief: str,
) -> list[str]:
    from services import post_ideas_gemini

    existing_ideas = (
        post_ideas_storage.load_post_ideas()
    )
    client_ai_context = build_client_ai_context(client)
    generated_ideas = (
        post_ideas_gemini.generate_gemini_post_ideas(
            client_ai_context,
            brief,
            existing_ideas,
        )
    )

    return list(generated_ideas.ideas)


def generate_openai_post_idea_candidates(
    client: Client | None,
    brief: str,
) -> list[str]:
    from services import post_ideas_openai

    existing_ideas = (
        post_ideas_storage.load_post_ideas()
    )
    client_ai_context = build_client_ai_context(client)
    generated_ideas = (
        post_ideas_openai.generate_openai_post_ideas(
            client_ai_context,
            brief,
            existing_ideas,
        )
    )

    return list(generated_ideas.ideas)


def generate_groq_post_idea_candidates(
    client: Client | None,
    brief: str,
) -> list[str]:
    from services import post_ideas_groq

    existing_ideas = (
        post_ideas_storage.load_post_ideas()
    )
    client_ai_context = build_client_ai_context(client)
    generated_ideas = (
        post_ideas_groq.generate_groq_post_ideas(
            client_ai_context,
            brief,
            existing_ideas,
        )
    )

    return list(generated_ideas.ideas)


def save_selected_post_ideas(
    selected_ideas: list[str],
) -> tuple[list[str], list[str]]:
    post_ideas = post_ideas_storage.load_post_ideas()
    updated_post_ideas = list(post_ideas)
    added_ideas = []
    duplicate_ideas = []

    for idea in selected_ideas:
        formatted_idea = format_post_idea(idea)

        if post_idea_exists(
            formatted_idea,
            updated_post_ideas,
        ):
            duplicate_ideas.append(formatted_idea)
            continue

        updated_post_ideas.append(formatted_idea)
        added_ideas.append(formatted_idea)

    if added_ideas:
        post_ideas_storage.save_all_post_ideas(
            updated_post_ideas
        )

    return added_ideas, duplicate_ideas


def delete_post_idea(
    number_text,
    displayed_post_ideas=None,
):
    current_post_ideas = post_ideas_storage.load_post_ideas()

    if displayed_post_ideas is None:
        displayed_post_ideas = current_post_ideas

    (
        selection_status,
        idea_number,
        selected_idea,
    ) = select_post_idea_by_number(
        displayed_post_ideas,
        number_text,
    )

    if selection_status != IDEA_OPERATION_READY:
        return selection_status, None, current_post_ideas

    if not is_current_post_idea_selection(
        current_post_ideas,
        idea_number,
        selected_idea,
    ):
        return (
            IDEA_SELECTION_STALE,
            None,
            current_post_ideas,
        )

    (
        _,
        _,
        remaining_post_ideas,
    ) = prepare_post_idea_deletion(
        current_post_ideas,
        number_text,
    )
    formatted_remaining_post_ideas = [
        format_post_idea(idea)
        for idea in remaining_post_ideas
    ]
    post_ideas_storage.save_all_post_ideas(
        formatted_remaining_post_ideas
    )

    return (
        IDEA_OPERATION_READY,
        selected_idea,
        formatted_remaining_post_ideas,
    )


def edit_post_idea(
    idea_number,
    selected_idea,
    new_idea,
):
    current_post_ideas = post_ideas_storage.load_post_ideas()

    if not is_current_post_idea_selection(
        current_post_ideas,
        idea_number,
        selected_idea,
    ):
        return (
            IDEA_SELECTION_STALE,
            None,
            current_post_ideas,
        )

    duplicate_exists = post_idea_exists(
        new_idea,
        current_post_ideas,
    )
    (
        edit_status,
        formatted_idea,
        updated_post_ideas,
    ) = prepare_post_idea_edit(
        current_post_ideas,
        idea_number,
        new_idea,
        duplicate_exists,
    )

    if edit_status == IDEA_DUPLICATE:
        return edit_status, formatted_idea, current_post_ideas

    formatted_post_ideas = [
        format_post_idea(idea)
        for idea in updated_post_ideas
    ]
    post_ideas_storage.save_all_post_ideas(
        formatted_post_ideas
    )

    return (
        IDEA_OPERATION_READY,
        formatted_idea,
        formatted_post_ideas,
    )