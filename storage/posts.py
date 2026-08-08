import json


POSTS_FILE = "posts.txt"


def load_posts():
    try:
        with open(POSTS_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

            if isinstance(data, list):
                return data

            return []

    except FileNotFoundError:
        return []

    except json.JSONDecodeError:
        return []


def save_posts(posts):
    with open(POSTS_FILE, "w", encoding="utf-8") as file:
        json.dump(
            posts,
            file,
            ensure_ascii=False,
            indent=4,
        )
