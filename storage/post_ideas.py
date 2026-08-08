POST_IDEAS_FILE = "post_ideas.txt"


def load_post_ideas():
    try:
        with open(POST_IDEAS_FILE, "r", encoding="utf-8") as file:
            return [
                line.strip()
                for line in file.readlines()
                if line.strip()
            ]
    except FileNotFoundError:
        return []


def save_all_post_ideas(post_ideas):
    with open(POST_IDEAS_FILE, "w", encoding="utf-8") as file:
        for idea in post_ideas:
            file.write(idea + "\n")


def add_post_idea_to_file(idea):
    with open(POST_IDEAS_FILE, "a+", encoding="utf-8") as file:
        file.seek(0, 2)

        if file.tell() > 0:
            file.seek(file.tell() - 1)
            last_symbol = file.read(1)

            if last_symbol != "\n":
                file.write("\n")

        file.write(idea + "\n")
