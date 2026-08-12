from models.client import Client
from storage import clients as clients_storage


CLIENT_FIELD_KEYS = {
    "Имя": "name",
    "Фамилия": "last_name",
    "Телефон": "phone",
    "Instagram": "instagram",
    "Email": "email",
    "Заметки": "notes",
}

CLIENT_CREATED = "created"
CLIENT_DELETED = "deleted"
CLIENT_UPDATED = "updated"
CLIENT_UNCHANGED = "unchanged"
CLIENT_DUPLICATE = "duplicate"
CLIENT_NOT_FOUND = "not_found"


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


def load_clients() -> list[Client]:
    return clients_storage.load_clients()


def get_client_by_full_name(
    name: str,
    last_name: str,
) -> Client | None:
    return find_client_by_full_name(
        load_clients(),
        name,
        last_name,
    )


def current_client_exists(
    name: str,
    last_name: str,
) -> bool:
    return get_client_by_full_name(
        name,
        last_name,
    ) is not None


def create_client(client: Client) -> str:
    clients = load_clients()

    if client_exists(
        clients,
        client["name"],
        client["last_name"],
    ):
        return CLIENT_DUPLICATE

    clients.append(dict(client))
    clients_storage.save_clients(clients)

    return CLIENT_CREATED


def delete_client(
    name: str,
    last_name: str,
) -> str:
    clients = load_clients()
    client = find_client_by_full_name(
        clients,
        name,
        last_name,
    )

    if client is None:
        return CLIENT_NOT_FOUND

    clients.remove(client)
    clients_storage.save_clients(clients)

    return CLIENT_DELETED


def edit_client_field(
    name: str,
    last_name: str,
    field_key: str,
    new_value: str,
) -> tuple[str, Client | None]:
    clients = load_clients()
    client = find_client_by_full_name(
        clients,
        name,
        last_name,
    )

    if client is None:
        return CLIENT_NOT_FOUND, None

    old_name = client["name"]
    old_last_name = client["last_name"]

    if field_key == "name" and client_exists(
        clients,
        new_value,
        old_last_name,
    ):
        return CLIENT_DUPLICATE, client

    if field_key == "last_name" and client_exists(
        clients,
        old_name,
        new_value,
    ):
        return CLIENT_DUPLICATE, client

    if client[field_key] == new_value:
        return CLIENT_UNCHANGED, client

    client[field_key] = new_value
    clients_storage.save_clients(clients)

    return CLIENT_UPDATED, client


def search_clients(search_text: str) -> list[Client]:
    normalized_search_text = search_text.lower()

    return [
        client
        for client in load_clients()
        if normalized_search_text
        in f"{client['name']} {client['last_name']}".lower()
    ]
