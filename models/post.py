from typing import TypedDict

from models.client import Client


class Post(TypedDict):
    id: int
    client: str
    client_context: Client | None
    topic: str
    style: str
    text: str
