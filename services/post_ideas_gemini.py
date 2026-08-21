import httpx
from pydantic import ValidationError

from models.post_idea import GeneratedPostIdeas
from services.post_ideas import (
    POST_IDEAS_AI_CONTRACT,
    PostIdeasGenerationError,
    format_existing_post_ideas,
)


GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_THINKING_LEVEL = "low"

# Compatibility name for existing tests and imports. Product rules are shared
# with every Post Ideas provider.
POST_IDEAS_INSTRUCTIONS = POST_IDEAS_AI_CONTRACT


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


def generate_gemini_post_ideas(
    client_ai_context: str,
    brief: str,
    existing_ideas: list[str],
) -> GeneratedPostIdeas:
    # Local imports keep manual Post Ideas scenarios importable when the
    # optional Gemini dependency is not installed in the environment.
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

        raise PostIdeasGenerationError(
            "Не удалось авторизоваться в Gemini. "
            "Проверьте настройку API и повторите позже."
        ) from error

    client_context_text = (
        client_ai_context
        if client_ai_context
        else "Не указан."
    )
    existing_ideas_text = format_existing_post_ideas(
        existing_ideas
    )

    try:
        interaction = client.interactions.create(
            model=GEMINI_MODEL,
            input=(
                "Контекст клиента:\n"
                f"{client_context_text}\n\n"
                "Бриф или тема пользователя:\n"
                f"{brief}\n\n"
                "Существующие идеи, которые не нужно повторять:\n"
                f"{existing_ideas_text}"
            ),
            system_instruction=POST_IDEAS_INSTRUCTIONS,
            generation_config={
                "thinking_level": GEMINI_THINKING_LEVEL,
            },
            store=False,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": GeneratedPostIdeas.model_json_schema(),
            },
        )

    except genai_errors.ClientError as error:
        if _is_authentication_error(error):
            raise PostIdeasGenerationError(
                "Не удалось авторизоваться в Gemini. "
                "Проверьте настройку API и повторите позже."
            ) from error

        if getattr(error, "code", None) == 429:
            raise PostIdeasGenerationError(
                "Gemini временно ограничил число запросов. "
                "Попробуйте ещё раз немного позже."
            ) from error

        raise PostIdeasGenerationError(
            "Gemini вернул ошибку сервиса. "
            "Идеи не созданы; попробуйте позже."
        ) from error

    except genai_errors.ServerError as error:
        raise PostIdeasGenerationError(
            "Gemini вернул ошибку сервиса. "
            "Идеи не созданы; попробуйте позже."
        ) from error

    except genai_errors.APIError as error:
        raise PostIdeasGenerationError(
            "Не удалось получить ответ Gemini. "
            "Идеи не созданы; попробуйте позже."
        ) from error

    except genai_errors.UnknownApiResponseError as error:
        raise PostIdeasGenerationError(
            "Не удалось получить ответ Gemini. "
            "Идеи не созданы; попробуйте позже."
        ) from error

    except (
        GeminiAPIConnectionError,
        httpx.RequestError,
    ) as error:
        raise PostIdeasGenerationError(
            "Gemini сейчас не отвечает. "
            "Проверьте интернет-соединение "
            "и попробуйте ещё раз."
        ) from error

    output_text = getattr(
        interaction,
        "output_text",
        None,
    )

    if not isinstance(output_text, str) or not output_text.strip():
        raise PostIdeasGenerationError(
            "Gemini не сформировал идеи постов. "
            "Ничего не сохранено; попробуйте ещё раз."
        )

    try:
        generated_ideas = GeneratedPostIdeas.model_validate_json(
            output_text
        )

    except ValidationError as error:
        raise PostIdeasGenerationError(
            "Gemini вернул некорректный список идей. "
            "Ничего не сохранено; попробуйте ещё раз."
        ) from error

    if (
        len(generated_ideas.ideas) != 3
        or any(not idea for idea in generated_ideas.ideas)
    ):
        raise PostIdeasGenerationError(
            "Gemini вернул некорректный список идей. "
            "Ничего не сохранено; попробуйте ещё раз."
        )

    return generated_ideas
