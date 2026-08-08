from models.client import Client
from models.post import Post
from storage import posts as posts_storage


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
) -> Post:
    post_id = get_next_post_id(posts)
    post_text = create_post_text(
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
        "text": post_text,
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
