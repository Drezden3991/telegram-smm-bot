from models.client import Client
from models.post import Post
from storage import posts as posts_storage


class WritePostGenerationError(Exception):
    pass


WRITE_POST_AI_CONTRACT = (
    "Ты опытный SMM-копирайтер для Telegram. Напиши один готовый "
    "SMM-пост на русском языке по переданным безопасному контексту "
    "клиента, теме и стилю. Учитывай выбранный стиль: Экспертный, "
    "Продающий, Дружелюбный или Информационный.\n\n"
    "ПОДТВЕРЖДЁННЫЕ ФАКТЫ О КЛИЕНТЕ — это только сведения, явно "
    "указанные во входном контексте. Не выдумывай и не приписывай "
    "клиенту цены, скидки, акции, промокоды, адреса, контакты, часы "
    "работы, товары, услуги, инфраструктуру, отзывы, награды, "
    "сертификаты, цифры и другие конкретные бизнес-факты, если их нет "
    "во входных данных.\n\n"
    "ОБЩИЕ ЗНАНИЯ допустимы только как нейтральный контент; не "
    "превращай их в утверждения о конкретном клиенте. Если данных "
    "недостаточно, пиши нейтрально, а не достраивай детали. Избегай "
    "ложных утверждений от имени бизнеса. В безопасном контексте нет "
    "телефона и email: не добавляй их в текст.\n\n"
    "Верни только готовый черновик поста для SMM-специалиста: без "
    "технических комментариев, объяснений процесса и JSON."
)


def get_next_post_id(posts: list[Post]) -> int:
    if not posts:
        return 1

    existing_ids = [
        post.get("id", 0)
        for post in posts
        if isinstance(post.get("id"), int)
    ]

    if not existing_ids:
        return 1

    return max(existing_ids) + 1


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


def clean_idea_text(idea: str) -> str:
    if idea.startswith("💡 "):
        return idea[2:].strip()

    return idea.strip()


def filter_ideas(
    ideas: list[str],
    excluded_text: str,
) -> list[str]:
    return [
        idea
        for idea in ideas
        if excluded_text not in idea
    ]


def get_selected_item(
    items: list[str],
    text: str,
) -> int | None:
    for number, item in enumerate(items, start=1):
        expected_text = f"{number}. {item}"

        if text == expected_text:
            return number - 1

    return None


def create_post_text(
    client_name: str,
    topic: str,
    style: str,
) -> str:
    if client_name:
        client_text = client_name
    else:
        client_text = "вашего проекта"

    if style == "Экспертный":
        return (
            f"📝 Пост для: {client_text}\n\n"
            f"Тема: {topic}\n\n"
            "Сегодня важно говорить не просто о продукте, "
            "а о пользе, которую он даёт клиенту.\n\n"
            f"{topic} — это тема, которая помогает показать "
            "экспертность, раскрыть ценность услуги и объяснить "
            "аудитории, почему ей стоит обратить внимание именно сейчас.\n\n"
            "Хороший SMM начинается не с красивой картинки, "
            "а с понимания боли клиента и сильного сообщения."
        )

    if style == "Продающий":
        return (
            f"📝 Пост для: {client_text}\n\n"
            f"Тема: {topic}\n\n"
            "Если вы давно думали об этом, сейчас хороший момент начать.\n\n"
            f"{topic} помогает решить конкретную задачу клиента "
            "и сделать первый шаг к результату.\n\n"
            "Напишите нам, если хотите узнать больше "
            "или подобрать решение под вашу ситуацию."
        )

    if style == "Дружелюбный":
        return (
            f"📝 Пост для: {client_text}\n\n"
            f"Тема: {topic}\n\n"
            f"Давайте поговорим о теме: {topic}.\n\n"
            "Это может казаться простой вещью, но именно из таких деталей "
            "часто складывается доверие, интерес и желание узнать больше.\n\n"
            "А как вы относитесь к этой теме?"
        )

    return (
        f"📝 Пост для: {client_text}\n\n"
        f"Тема: {topic}\n\n"
        f"{topic} — важная тема для продвижения "
        "и общения с аудиторией.\n\n"
        "Она помогает рассказать о продукте, показать пользу "
        "и объяснить, почему это может быть актуально для клиента.\n\n"
        "Регулярный контент помогает бренду оставаться "
        "заметным и понятным для своей аудитории."
    )


def build_post(
    posts: list[Post],
    client_name: str,
    client_context: Client | None,
    topic: str,
    style: str,
    text: str | None = None,
) -> Post:
    post_id = get_next_post_id(posts)

    if text is None:
        text = create_post_text(
            client_name,
            topic,
            style,
        )

    return {
        "id": post_id,
        "client": client_name,
        "client_context": client_context,
        "topic": topic,
        "style": style,
        "text": text,
    }


def create_and_save_post(
    client_name: str,
    client_context: Client | None,
    topic: str,
    style: str,
) -> Post:
    posts = posts_storage.load_posts()
    post = build_post(
        posts,
        client_name,
        client_context,
        topic,
        style,
    )

    posts.append(post)
    posts_storage.save_posts(posts)

    return post


def create_and_save_gemini_post(
    client_name: str,
    client_context: Client | None,
    topic: str,
    style: str,
) -> Post:
    from services import write_post_gemini

    client_ai_context = build_client_ai_context(
        client_context
    )
    generated_text = (
        write_post_gemini.generate_gemini_post(
            client_ai_context,
            topic,
            style,
        )
    )

    posts = posts_storage.load_posts()
    post = build_post(
        posts,
        client_name,
        client_context,
        topic,
        style,
        text=generated_text,
    )

    posts.append(post)
    posts_storage.save_posts(posts)

    return post


def create_and_save_openai_post(
    client_name: str,
    client_context: Client | None,
    topic: str,
    style: str,
) -> Post:
    from services import write_post_openai

    client_ai_context = build_client_ai_context(
        client_context
    )
    generated_text = (
        write_post_openai.generate_openai_post(
            client_ai_context,
            topic,
            style,
        )
    )

    posts = posts_storage.load_posts()
    post = build_post(
        posts,
        client_name,
        client_context,
        topic,
        style,
        text=generated_text,
    )

    posts.append(post)
    posts_storage.save_posts(posts)

    return post


def create_and_save_groq_post(
    client_name: str,
    client_context: Client | None,
    topic: str,
    style: str,
) -> Post:
    from services import write_post_groq

    client_ai_context = build_client_ai_context(
        client_context
    )
    generated_text = write_post_groq.generate_groq_post(
        client_ai_context,
        topic,
        style,
    )

    posts = posts_storage.load_posts()
    post = build_post(
        posts,
        client_name,
        client_context,
        topic,
        style,
        text=generated_text,
    )

    posts.append(post)
    posts_storage.save_posts(posts)

    return post


def find_posts(
    posts: list[Post],
    query: str,
) -> list[Post]:
    normalized_query = query.lower().strip()
    found_posts = []

    for post in posts:
        client = str(post.get("client", "")).lower()
        topic = str(post.get("topic", "")).lower()
        style = str(post.get("style", "")).lower()
        text = str(post.get("text", "")).lower()

        if (
            normalized_query in client
            or normalized_query in topic
            or normalized_query in style
            or normalized_query in text
        ):
            found_posts.append(post)

    return found_posts


def get_last_posts(posts: list[Post]) -> list[Post]:
    return posts[-10:]


def prepare_post_deletion(
    posts: list[Post],
    post_id: int,
) -> tuple[bool, list[Post]]:
    updated_posts = [
        post
        for post in posts
        if post.get("id") != post_id
    ]

    post_was_deleted = len(updated_posts) != len(posts)

    return post_was_deleted, updated_posts


def delete_post(post_id: int) -> tuple[bool, Post | None]:
    posts = posts_storage.load_posts()
    deleted_post = next(
        (post for post in posts if post.get("id") == post_id),
        None,
    )
    post_was_deleted, updated_posts = prepare_post_deletion(
        posts,
        post_id,
    )

    if not post_was_deleted:
        return False, None

    posts_storage.save_posts(updated_posts)

    return True, deleted_post