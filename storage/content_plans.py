CONTENT_PLANS_FILE = "content_plans.txt"

SEPARATOR = "-" * 40


def read_content_plans():
    try:
        with open(
            CONTENT_PLANS_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            content = file.read().strip()

    except FileNotFoundError:
        return []

    if not content:
        return []

    content_plans = content.split(SEPARATOR)

    return [
        content_plan.strip()
        for content_plan in content_plans
        if content_plan.strip()
    ]


def save_content_plans(content_plans):
    with open(
        CONTENT_PLANS_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        for content_plan in content_plans:
            file.write(content_plan.strip())
            file.write("\n")
            file.write(SEPARATOR)
            file.write("\n")
