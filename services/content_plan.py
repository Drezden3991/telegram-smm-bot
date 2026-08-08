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
