from models.client import Client


CLIENTS_FILE = "clients.txt"
CLIENT_FIELD_SEPARATOR = " | "


def create_client_from_line(line: str) -> Client:
    parts = line.split(CLIENT_FIELD_SEPARATOR)

    if len(parts) == 6:
        return {
            "name": parts[0],
            "last_name": parts[1],
            "phone": parts[2],
            "instagram": parts[3],
            "email": parts[4],
            "notes": parts[5],
        }

    if len(parts) == 5:
        return {
            "name": parts[0],
            "last_name": "",
            "phone": parts[1],
            "instagram": parts[2],
            "email": parts[3],
            "notes": parts[4],
        }

    return {
        "name": line,
        "last_name": "",
        "phone": "",
        "instagram": "",
        "email": "",
        "notes": "",
    }


def create_line_from_client(client: Client) -> str:
    return CLIENT_FIELD_SEPARATOR.join(
        [
            client["name"],
            client["last_name"],
            client["phone"],
            client["instagram"],
            client["email"],
            client["notes"],
        ]
    )


def load_clients() -> list[Client]:
    clients: list[Client] = []

    try:
        with open(CLIENTS_FILE, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()

                if not line:
                    continue

                clients.append(create_client_from_line(line))
    except FileNotFoundError:
        pass

    return clients


def save_clients(clients: list[Client]) -> None:
    with open(CLIENTS_FILE, "w", encoding="utf-8") as file:
        for client in clients:
            file.write(create_line_from_client(client) + "\n")
