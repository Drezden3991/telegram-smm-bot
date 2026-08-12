import os

from services.write_post import (
    WRITE_POST_AI_CONTRACT,
    WritePostGenerationError,
)


GROQ_MODEL = "openai/gpt-oss-120b"
GROQ_REASONING_EFFORT = "low"


def generate_groq_post(
    client_ai_context: str,
    topic: str,
    style: str,
) -> str:
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise WritePostGenerationError(
            "Не удалось авторизоваться в Groq. "
            "Проверьте настройку API и повторите позже."
        )

    # The import is local so the existing template Telegram path remains
    # importable before the optional dependency is installed.
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

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": WRITE_POST_AI_CONTRACT,
                },
                {
                    "role": "user",
                    "content": (
                        "Контекст клиента:\n"
                        f"{client_context_text}\n\n"
                        "Тема поста:\n"
                        f"{topic}\n\n"
                        "Стиль поста:\n"
                        f"{style}"
                    ),
                },
            ],
            reasoning_effort=GROQ_REASONING_EFFORT,
        )

    except AuthenticationError as error:
        raise WritePostGenerationError(
            "Не удалось авторизоваться в Groq. "
            "Проверьте настройку API и повторите позже."
        ) from error

    except RateLimitError as error:
        raise WritePostGenerationError(
            "Groq временно ограничил число запросов. "
            "Попробуйте ещё раз немного позже."
        ) from error

    except (
        APITimeoutError,
        APIConnectionError,
    ) as error:
        raise WritePostGenerationError(
            "Groq сейчас не отвечает. "
            "Проверьте интернет-соединение и попробуйте ещё раз."
        ) from error

    except APIStatusError as error:
        raise WritePostGenerationError(
            "Groq вернул ошибку сервиса. "
            "Пост не сохранён; попробуйте позже."
        ) from error

    except GroqError as error:
        raise WritePostGenerationError(
            "Не удалось получить ответ Groq. "
            "Пост не сохранён; попробуйте позже."
        ) from error

    try:
        output_text = response.choices[0].message.content

    except (
        AttributeError,
        IndexError,
        TypeError,
    ) as error:
        raise WritePostGenerationError(
            "Groq не сформировал текст поста. "
            "Пост не сохранён; попробуйте ещё раз."
        ) from error

    if (
        not isinstance(output_text, str)
        or not output_text.strip()
    ):
        raise WritePostGenerationError(
            "Groq не сформировал текст поста. "
            "Пост не сохранён; попробуйте ещё раз."
        )

    return output_text.strip()
