from models.client import Client


CLIENT_FIELD_KEYS = {
    "Имя": "name",
    "Фамилия": "last_name",
    "Телефон": "phone",
    "Instagram": "instagram",
    "Email": "email",
    "Заметки": "notes",
}


def find_client_by_full_name(
    clients: list[Client],
    name: str,
    last_name: str,
) -> Client | None:
    for client in clients:
        if (
            client["name"].lower() == name.lower()
            and client["last_name"].lower() == last_name.lower()
        ):
            return client

    return None


def client_exists(
    clients: list[Client],
    name: str,
    last_name: str,
) -> bool:
    return find_client_by_full_name(
        clients,
        name,
        last_name,
    ) is not None


def get_field_key(field_name: str) -> str:
    return CLIENT_FIELD_KEYS.get(field_name, "")
