import os

from pydantic import ValidationError

from models.content_plan import SevenDayContentPlan
from services.content_plan import (
    CONTENT_PLAN_AI_CONTRACT,
    ContentPlanGenerationError,
)


GROQ_MODEL = "openai/gpt-oss-120b"
GROQ_REASONING_EFFORT = "low"


def generate_groq_content_plan(
    brief: str,
) -> SevenDayContentPlan:
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ContentPlanGenerationError(
            "Не удалось авторизоваться в Groq. "
            "Проверьте настройку API и повторите позже."
        )

    # The import is local so the existing Telegram/OpenAI path remains
    # importable before the newly pinned Groq dependency is installed.
    from groq import (
        APIConnectionError,
        APIStatusError,
        APITimeoutError,
        AuthenticationError,
        Groq,
        GroqError,
        RateLimitError,
    )

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": CONTENT_PLAN_AI_CONTRACT,
                },
                {
                    "role": "user",
                    "content": (
                        "Краткий бриф пользователя:\n"
                        f"{brief}"
                    ),
                },
            ],
            reasoning_effort=GROQ_REASONING_EFFORT,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "seven_day_content_plan",
                    "strict": True,
                    "schema": SevenDayContentPlan.model_json_schema(),
                },
            },
        )

    except AuthenticationError as error:
        raise ContentPlanGenerationError(
            "Не удалось авторизоваться в Groq. "
            "Проверьте настройку API и повторите позже."
        ) from error

    except RateLimitError as error:
        raise ContentPlanGenerationError(
            "Groq временно ограничил число запросов. "
            "Попробуйте ещё раз немного позже."
        ) from error

    except (
        APITimeoutError,
        APIConnectionError,
    ) as error:
        raise ContentPlanGenerationError(
            "Groq сейчас не отвечает. "
            "Проверьте интернет-соединение и попробуйте ещё раз."
        ) from error

    except APIStatusError as error:
        raise ContentPlanGenerationError(
            "Groq вернул ошибку сервиса. "
            "Контент-план не сохранён; попробуйте позже."
        ) from error

    except GroqError as error:
        raise ContentPlanGenerationError(
            "Не удалось получить ответ Groq. "
            "Контент-план не сохранён; попробуйте позже."
        ) from error

    try:
        output_text = response.choices[0].message.content

    except (
        AttributeError,
        IndexError,
        TypeError,
    ) as error:
        raise ContentPlanGenerationError(
            "Groq не сформировал контент-план. "
            "Ничего не сохранено; попробуйте ещё раз."
        ) from error

    if not output_text or not output_text.strip():
        raise ContentPlanGenerationError(
            "Groq не сформировал контент-план. "
            "Ничего не сохранено; попробуйте ещё раз."
        )

    try:
        content_plan = SevenDayContentPlan.model_validate_json(
            output_text
        )

    except ValidationError as error:
        raise ContentPlanGenerationError(
            "Groq вернул неполный контент-план. "
            "Ничего не сохранено; попробуйте ещё раз."
        ) from error

    days = [
        item.day
        for item in content_plan.days
    ]

    if days != list(range(1, 8)):
        raise ContentPlanGenerationError(
            "Groq вернул дни в неверном порядке. "
            "Ничего не сохранено; попробуйте ещё раз."
        )

    return content_plan
