import httpx
from pydantic import ValidationError

from models.content_plan import SevenDayContentPlan
from services.content_plan import (
    CONTENT_PLAN_AI_CONTRACT,
    ContentPlanGenerationError,
)


GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_THINKING_LEVEL = "low"

# Compatibility name for the earlier Gemini-focused tests and imports. The
# product contract itself is shared by every Content Plan provider.
GEMINI_CONTENT_PLAN_INSTRUCTIONS = CONTENT_PLAN_AI_CONTRACT


def _is_missing_api_key_error(error):
    message = str(error).lower()

    return "api_key" in message and (
        "missing" in message
        or "provide" in message
    )


def _is_authentication_error(error):
    if getattr(error, "code", None) in (401, 403):
        return True

    message = str(error).lower()

    return (
        "api_key_invalid" in message
        or "invalid api key" in message
    )


def generate_gemini_content_plan(
    brief: str,
) -> SevenDayContentPlan:
    # Imports are local so the existing OpenAI scenario remains importable
    # before the newly pinned dependency is installed.
    from google import genai
    from google.genai import errors as genai_errors
    from google.genai._gaos.lib.compat_errors import (
        APIConnectionError as GeminiAPIConnectionError,
    )

    try:
        client = genai.Client()

    except ValueError as error:
        if not _is_missing_api_key_error(error):
            raise

        raise ContentPlanGenerationError(
            "Не удалось авторизоваться в Gemini. "
            "Проверьте настройку API и повторите позже."
        ) from error

    try:
        interaction = client.interactions.create(
            model=GEMINI_MODEL,
            input=(
                "Краткий бриф пользователя:\n"
                f"{brief}"
            ),
            system_instruction=(
                GEMINI_CONTENT_PLAN_INSTRUCTIONS
            ),
            generation_config={
                "thinking_level": GEMINI_THINKING_LEVEL,
            },
            store=False,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": SevenDayContentPlan.model_json_schema(),
            },
        )

    except genai_errors.ClientError as error:
        if _is_authentication_error(error):
            raise ContentPlanGenerationError(
                "Не удалось авторизоваться в Gemini. "
                "Проверьте настройку API и повторите позже."
            ) from error

        if getattr(error, "code", None) == 429:
            raise ContentPlanGenerationError(
                "Gemini временно ограничил число запросов. "
                "Попробуйте ещё раз немного позже."
            ) from error

        raise ContentPlanGenerationError(
            "Gemini вернул ошибку сервиса. "
            "Контент-план не сохранён; "
            "попробуйте позже."
        ) from error

    except genai_errors.ServerError as error:
        raise ContentPlanGenerationError(
            "Gemini вернул ошибку сервиса. "
            "Контент-план не сохранён; "
            "попробуйте позже."
        ) from error

    except genai_errors.APIError as error:
        raise ContentPlanGenerationError(
            "Не удалось получить ответ Gemini. "
            "Контент-план не сохранён; "
            "попробуйте позже."
        ) from error

    except genai_errors.UnknownApiResponseError as error:
        raise ContentPlanGenerationError(
            "Не удалось получить ответ Gemini. "
            "Контент-план не сохранён; "
            "попробуйте позже."
        ) from error

    except (
        GeminiAPIConnectionError,
        httpx.RequestError,
    ) as error:
        raise ContentPlanGenerationError(
            "Gemini сейчас не отвечает. "
            "Проверьте интернет-соединение "
            "и попробуйте ещё раз."
        ) from error

    output_text = interaction.output_text

    if not output_text or not output_text.strip():
        raise ContentPlanGenerationError(
            "Gemini не сформировал контент-план. "
            "Ничего не сохранено; "
            "попробуйте ещё раз."
        )

    try:
        content_plan = SevenDayContentPlan.model_validate_json(
            output_text
        )

    except ValidationError as error:
        raise ContentPlanGenerationError(
            "Gemini вернул неполный контент-план. "
            "Ничего не сохранено; "
            "попробуйте ещё раз."
        ) from error

    days = [
        item.day
        for item in content_plan.days
    ]

    if days != list(range(1, 8)):
        raise ContentPlanGenerationError(
            "Gemini вернул дни в неверном порядке. "
            "Ничего не сохранено; "
            "попробуйте ещё раз."
        )

    return content_plan
