import random

from storage import post_ideas as post_ideas_storage


IDEA_OPERATION_READY = "ready"
IDEA_NUMBER_NOT_DIGIT = "number_not_digit"
IDEA_NUMBER_NOT_FOUND = "number_not_found"
IDEA_DUPLICATE = "duplicate"


def format_post_idea(idea):
    idea = idea.strip()

    if not idea.startswith("💡"):
        idea = "💡 " + idea

    return idea


def normalize_post_idea(idea):
    idea = idea.strip().lower()

    if idea.startswith("💡"):
        idea = idea[1:].strip()

    return idea


def post_idea_exists(new_idea, post_ideas=None):
    if post_ideas is None:
        post_ideas = post_ideas_storage.load_post_ideas()

    normalized_new_idea = normalize_post_idea(new_idea)

    for idea in post_ideas:
        if normalize_post_idea(idea) == normalized_new_idea:
            return True

    return False


def find_post_ideas(post_ideas, search_text):
    normalized_search_text = search_text.lower().strip()

    return [
        (number, idea)
        for number, idea in enumerate(post_ideas, start=1)
        if normalized_search_text in idea.lower()
    ]


def choose_random_post_idea(post_ideas):
    return random.choice(post_ideas)


def select_post_idea_by_number(post_ideas, number_text):
    if not number_text.isdigit():
        return IDEA_NUMBER_NOT_DIGIT, None, None

    idea_number = int(number_text)

    if idea_number < 1 or idea_number > len(post_ideas):
        return IDEA_NUMBER_NOT_FOUND, None, None

    return (
        IDEA_OPERATION_READY,
        idea_number,
        post_ideas[idea_number - 1],
    )


def prepare_post_idea_deletion(post_ideas, number_text):
    status, idea_number, selected_idea = select_post_idea_by_number(
        post_ideas,
        number_text,
    )

    if status != IDEA_OPERATION_READY:
        return status, None, None

    remaining_post_ideas = list(post_ideas)
    remaining_post_ideas.pop(idea_number - 1)

    return status, selected_idea, remaining_post_ideas


def is_current_post_idea_selection(
    post_ideas,
    idea_number,
    selected_idea,
):
    return (
        isinstance(idea_number, int)
        and idea_number >= 1
        and idea_number <= len(post_ideas)
        and post_ideas[idea_number - 1] == selected_idea
    )


def prepare_post_idea_edit(
    post_ideas,
    idea_number,
    new_idea,
    duplicate_exists,
):
    updated_post_ideas = list(post_ideas)
    old_idea = updated_post_ideas[idea_number - 1]

    if duplicate_exists:
        return IDEA_DUPLICATE, old_idea, updated_post_ideas

    formatted_idea = format_post_idea(new_idea)
    updated_post_ideas[idea_number - 1] = formatted_idea

    return IDEA_OPERATION_READY, formatted_idea, updated_post_ideas
