import os

from pydantic import ValidationError

from models.post_idea import GeneratedPostIdeas
from services.post_ideas import (
    POST_IDEAS_AI_CONTRACT,
    PostIdeasGenerationError,
    format_existing_post_ideas,
)


GROQ_MODEL = "openai/gpt-oss-120b"
GROQ_REASONING_EFFORT = "low"


def generate_groq_post_ideas(
    client_ai_context: str,
    brief: str,
    existing_ideas: list[str],
) -> GeneratedPostIdeas:
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise PostIdeasGenerationError(
            "Не удалось авторизоваться в Groq. "
            "Проверьте настройку API и повторите позже."
        )

    # The import is local so manual Post Ideas scenarios remain importable
    # before the optional dependency is installed.
    from groq import (
        APIConnectionError,
        APIStatusError,
        APITimeoutError,
        AuthenticationError,
        Groq,
        GroqError,
        RateLimitError,
    )

    client_context_text = (
        client_ai_context
        if client_ai_context
        else "Не указан."
    )
    existing_ideas_text = format_existing_post_ideas(
        existing_ideas
    )

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": POST_IDEAS_AI_CONTRACT,
                },
                {
                    "role": "user",
                    "content": (
                        "Контекст клиента:\n"
                        f"{client_context_text}\n\n"
                        "Бриф или тема пользователя:\n"
                        f"{brief}\n\n"
                        "Существующие идеи, которые не нужно повторять:\n"
                        f"{existing_ideas_text}"
                    ),
                },
            ],
            reasoning_effort=GROQ_REASONING_EFFORT,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "generated_post_ideas",
                    "strict": True,
                    "schema": GeneratedPostIdeas.model_json_schema(),
                },
            },
        )

    except AuthenticationError as error:
        raise PostIdeasGenerationError(
            "Не удалось авторизоваться в Groq. "
            "Проверьте настройку API и повторите позже."
        ) from error

    except RateLimitError as error:
        raise PostIdeasGenerationError(
            "Groq временно ограничил число запросов. "
            "Попробуйте ещё раз немного позже."
        ) from error

    except (
        APITimeoutError,
        APIConnectionError,
    ) as error:
        raise PostIdeasGenerationError(
            "Groq сейчас не отвечает. "
            "Проверьте интернет-соединение и попробуйте ещё раз."
        ) from error

    except APIStatusError as error:
        raise PostIdeasGenerationError(
            "Groq вернул ошибку сервиса. "
            "Идеи не созданы; попробуйте позже."
        ) from error

    except GroqError as error:
        raise PostIdeasGenerationError(
            "Не удалось получить ответ Groq. "
            "Идеи не созданы; попробуйте позже."
        ) from error

    try:
        output_text = response.choices[0].message.content

    except (
        AttributeError,
        IndexError,
        TypeError,
    ) as error:
        raise PostIdeasGenerationError(
            "Groq не сформировал идеи постов. "
            "Ничего не сохранено; попробуйте ещё раз."
        ) from error

    if not isinstance(output_text, str) or not output_text.strip():
        raise PostIdeasGenerationError(
            "Groq не сформировал идеи постов. "
            "Ничего не сохранено; попробуйте ещё раз."
        )

    try:
        generated_ideas = GeneratedPostIdeas.model_validate_json(
            output_text
        )

    except ValidationError as error:
        raise PostIdeasGenerationError(
            "Groq вернул некорректный список идей. "
            "Ничего не сохранено; попробуйте ещё раз."
        ) from error

    if (
        len(generated_ideas.ideas) != 3
        or any(not idea for idea in generated_ideas.ideas)
    ):
        raise PostIdeasGenerationError(
            "Groq вернул некорректный список идей. "
            "Ничего не сохранено; попробуйте ещё раз."
        )

    return generated_ideas
