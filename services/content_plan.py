import asyncio

from models.content_plan import ContentPlanDay, SevenDayContentPlan
from storage import content_plans as content_plans_storage


CONTENT_PLAN_AI_CONTRACT = (
    "Ты опытный SMM-стратег для Telegram. Создай практичный контент-план "
    "ровно на семь дней по пользовательскому брифу. Дни должны идти строго "
    "от 1 до 7 без повторов. Для каждого дня сформулируй отдельные цель, тему, "
    "формат публикации, ключевой тезис и призыв к действию. Соблюдай логику "
    "прогрева: знакомство и польза в начале, доверие и работа с возражениями "
    "в середине, целевое действие ближе к концу. Чередуй подходящие для Telegram "
    "форматы. Если пользователь передал сохранённые идеи постов, используй их "
    "как дополнительный контекст и органично распределяй подходящие идеи по дням. "
    "Пиши на русском языке, конкретно и кратко. Не добавляй поля, которых нет "
    "в схеме, и не изменяй данные пользовательского брифа.\n\n"
    "Строго соблюдай максимальную длину каждого текстового поля: "
    "goal — не более 50 символов; "
    "topic — не более 90 символов; "
    "format — не более 30 символов; "
    "key_message — не более 120 символов; "
    "cta — не более 70 символов.\n\n"
    "ПОДТВЕРЖДЁННЫЕ ФАКТЫ О КЛИЕНТЕ — это только сведения, явно "
    "указанные во входном контексте. Любое утверждение о конкретном "
    "клиенте, его бизнесе, товарах, услугах, инфраструктуре, "
    "сотрудниках, условиях, ценах, акциях, адресах, контактах, часах "
    "работы, отзывах, наградах, сертификатах, статистике и других "
    "проверяемых свойствах разрешено, только если оно непосредственно "
    "следует из этих фактов. Отсутствие факта не означает, что он ложный, "
    "но не даёт права утверждать его существование.\n\n"
    "ОБЩИЕ ЗНАНИЯ можно использовать для нейтрального образовательного "
    "контента, но не превращай их в неподтверждённое утверждение о "
    "клиенте. Не заявляй от имени клиента наличие Wi-Fi, розеток, "
    "товаров или услуг, скидок, акций, промокодов, адресов, контактов, "
    "часов работы, инфраструктуры, отзывов, наград, сертификатов, "
    "статистики и других деталей, которых нет во входных данных.\n\n"
    "Разделяй ТЕМУ будущего поста и факт о клиенте: неизвестная деталь "
    "может быть темой, вопросом или направлением для раскрытия и уточнения, "
    "но не существующим свойством бизнеса. Не используй от имени клиента "
    "формулировки «у нас есть», «мы предлагаем», «наши гости», «в нашем "
    "меню», «наши бариста», «мы используем» или «у нас можно», если факт "
    "не подтверждён. key_message должен содержать только подтверждённый "
    "факт клиента, нейтральную общую мысль или тему, требующую уточнения. "
    "Если данных недостаточно, формулируй тему нейтрально; не заполняй "
    "пробелы правдоподобными догадками."
)

# Public compatibility name used by the existing handler and tests.
CONTENT_PLAN_INSTRUCTIONS = CONTENT_PLAN_AI_CONTRACT


class ContentPlanGenerationError(Exception):
    pass


CONTENT_PLAN_AI_PROVIDERS = (
    "openai",
    "gemini",
    "groq",
)

CONTENT_PLAN_SHORT_TITLE_MAX_LENGTH = 80
CONTENT_PLAN_CLIENT_TITLE_MAX_LENGTH = 30


def get_client_full_name(client):
    name = client.get("name", "").strip()
    last_name = client.get("last_name", "").strip()

    return f"{name} {last_name}".strip()


def get_selected_client(message_text, clients):
    for number, client in enumerate(clients, start=1):
        full_name = get_client_full_name(client)
        expected_text = f"{number}. {full_name}"

        if message_text == expected_text:
            return client

    return None


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


def toggle_selected_idea(
    selected_ideas,
    selected_idea,
):
    updated_selected_ideas = list(selected_ideas)

    if selected_idea in updated_selected_ideas:
        updated_selected_ideas.remove(selected_idea)
    else:
        updated_selected_ideas.append(selected_idea)

    return updated_selected_ideas


def reconcile_selected_ideas(
    selected_ideas,
    current_post_ideas,
):
    available_selected_ideas = [
        idea
        for idea in selected_ideas
        if idea in current_post_ideas
    ]
    missing_selected_ideas = [
        idea
        for idea in selected_ideas
        if idea not in current_post_ideas
    ]

    return (
        available_selected_ideas,
        missing_selected_ideas,
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

    result = "ВЫБРАННЫЕ ИДЕИ:\n"

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
            "ПОДТВЕРЖДЁННЫЕ ФАКТЫ О КЛИЕНТЕ:\n"
            f"{client_context}"
        )

    if ideas_context:
        brief_parts.append(ideas_context)

    brief_parts.append(
        "ПОЛЬЗОВАТЕЛЬСКАЯ ЗАДАЧА:\n"
        f"{user_brief}"
    )

    return "\n\n".join(brief_parts)


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


def _template_text(value, max_length):
    normalized_value = " ".join(str(value).split())

    if len(normalized_value) <= max_length:
        return normalized_value

    return normalized_value[: max_length - 1].rstrip() + "…"


def build_template_content_plan_text(client, selected_ideas, user_brief):
    """Build a deterministic seven-day content-plan draft without AI."""
    topics = [_template_text(idea, 90) for idea in selected_ideas]
    brief_topic = _template_text(f"Тема из брифа: {user_brief}", 90)
    goals = (
        "Познакомить с темой",
        "Показать практическую пользу",
        "Вовлечь аудиторию",
        "Раскрыть важный вопрос",
        "Поделиться полезным советом",
        "Собрать обратную связь",
        "Предложить следующий шаг",
    )
    formats = (
        "Текстовый пост",
        "Карточки",
        "Опрос",
        "Вопрос аудитории",
        "Чек-лист",
        "Короткое видео",
        "Итоговый пост",
    )
    content_plan = SevenDayContentPlan(
        days=[
            ContentPlanDay(
                day=day,
                goal=goals[day - 1],
                topic=(topics[day - 1] if day <= len(topics) else brief_topic),
                format=formats[day - 1],
                key_message=(
                    "Подготовьте публикацию по теме и уточните детали "
                    "перед публикацией."
                ),
                cta="Сохраните идею и уточните детали перед публикацией.",
            )
            for day in range(1, 8)
        ]
    )
    result = format_content_plan_text(
        get_client_full_name(client) if client else "",
        selected_ideas,
        user_brief,
        content_plan,
    )

    return result.replace("AI-", "", 1)


async def build_content_plan_text(
    client,
    selected_ideas,
    user_brief,
    provider="openai",
):
    if provider == "template":
        return build_template_content_plan_text(
            client,
            selected_ideas,
            user_brief,
        )

    ai_brief = build_ai_brief(
        client,
        selected_ideas,
        user_brief,
    )

    content_plan = await asyncio.to_thread(
        generate_content_plan,
        provider,
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


def generate_content_plan(
    provider: str,
    brief: str,
):
    if provider == "openai":
        from services import (
            content_plan_openai as content_plan_openai_service,
        )

        return content_plan_openai_service.generate_ai_content_plan(
            brief
        )

    if provider == "gemini":
        from services import (
            content_plan_gemini as content_plan_gemini_service,
        )

        return content_plan_gemini_service.generate_gemini_content_plan(
            brief
        )

    if provider == "groq":
        from services import (
            content_plan_groq as content_plan_groq_service,
        )

        return content_plan_groq_service.generate_groq_content_plan(
            brief
        )

    raise ValueError(
        f"Неизвестный AI-provider: {provider}"
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


def find_content_plans(content_plans, query):
    normalized_query = query.strip().lower()

    return [
        content_plan
        for content_plan in content_plans
        if normalized_query in content_plan.lower()
    ]


def is_current_content_plan_selection(
    content_plans,
    number,
    selected_content_plan,
):
    return (
        number is not None
        and number >= 1
        and number <= len(content_plans)
        and content_plans[number - 1] == selected_content_plan
    )


def prepare_content_plan_deletion(
    content_plans,
    number,
    selected_content_plan,
):
    if not is_current_content_plan_selection(
        content_plans,
        number,
        selected_content_plan,
    ):
        return False, None, list(content_plans)

    updated_content_plans = list(content_plans)
    deleted_content_plan = updated_content_plans.pop(
        number - 1
    )

    return True, deleted_content_plan, updated_content_plans


def prepare_content_plan_replacement(
    content_plans,
    number,
    selected_content_plan,
    updated_content_plan,
):
    if not is_current_content_plan_selection(
        content_plans,
        number,
        selected_content_plan,
    ):
        return False, list(content_plans)

    updated_content_plans = list(content_plans)
    updated_content_plans[number - 1] = updated_content_plan

    return True, updated_content_plans


def create_and_save_content_plan(
    content_plan,
    telegram_user_id: int | None = None,
):
    if telegram_user_id is None:
        content_plans_storage.add_content_plan(content_plan)
    else:
        content_plans_storage.add_content_plan(
            content_plan, telegram_user_id
        )

    return content_plan


def delete_content_plan(
    number,
    selected_content_plan,
    telegram_user_id: int | None = None,
):
    content_plans = content_plans_storage.read_content_plans(
        telegram_user_id
    )
    (
        content_plan_was_deleted,
        deleted_content_plan,
        updated_content_plans,
    ) = prepare_content_plan_deletion(
        content_plans,
        number,
        selected_content_plan,
    )

    if content_plan_was_deleted:
        if telegram_user_id is None:
            content_plans_storage.delete_content_plan_by_position(number)
        else:
            content_plans_storage.delete_content_plan_by_position(
                number, telegram_user_id
            )

    return (
        content_plan_was_deleted,
        deleted_content_plan,
        updated_content_plans,
    )


def replace_content_plan(
    number,
    selected_content_plan,
    updated_content_plan,
    telegram_user_id: int | None = None,
):
    content_plans = content_plans_storage.read_content_plans(
        telegram_user_id
    )
    (
        content_plan_was_replaced,
        updated_content_plans,
    ) = prepare_content_plan_replacement(
        content_plans,
        number,
        selected_content_plan,
        updated_content_plan,
    )

    if content_plan_was_replaced:
        if telegram_user_id is None:
            content_plans_storage.update_content_plan_by_position(
                number, updated_content_plan
            )
        else:
            content_plans_storage.update_content_plan_by_position(
                number, updated_content_plan, telegram_user_id
            )

    return content_plan_was_replaced, updated_content_plans
