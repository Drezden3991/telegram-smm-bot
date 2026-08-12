import httpx

from services.write_post import (
    WRITE_POST_AI_CONTRACT,
    WritePostGenerationError,
)


GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_THINKING_LEVEL = "low"

# Compatibility name for existing tests and imports. Product rules are shared
# with every Write Post provider.
WRITE_POST_INSTRUCTIONS = WRITE_POST_AI_CONTRACT


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


def generate_gemini_post(
    client_ai_context: str,
    topic: str,
    style: str,
) -> str:
    # Local imports keep the existing template path importable when the
    # optional Gemini dependency is not installed in the environment.
    from google import genai
    from google.genai import errors as genai_errors

    try:
        client = genai.Client()

    except ValueError as error:
        if not _is_missing_api_key_error(error):
            raise

        raise WritePostGenerationError(
            "Не удалось авторизоваться в Gemini. "
            "Проверьте настройку API и повторите позже."
        ) from error

    client_context_text = (
        client_ai_context
        if client_ai_context
        else "Не указан."
    )

    try:
        interaction = client.interactions.create(
            model=GEMINI_MODEL,
            input=(
                "Контекст клиента:\n"
                f"{client_context_text}\n\n"
                "Тема поста:\n"
                f"{topic}\n\n"
                "Стиль поста:\n"
                f"{style}"
            ),
            system_instruction=WRITE_POST_INSTRUCTIONS,
            generation_config={
                "thinking_level": GEMINI_THINKING_LEVEL,
            },
            store=False,
            response_format={
                "type": "text",
            },
        )

    except genai_errors.ClientError as error:
        if _is_authentication_error(error):
            raise WritePostGenerationError(
                "Не удалось авторизоваться в Gemini. "
                "Проверьте настройку API и повторите позже."
            ) from error

        if getattr(error, "code", None) == 429:
            raise WritePostGenerationError(
                "Gemini временно ограничил число запросов. "
                "Попробуйте ещё раз немного позже."
            ) from error

        raise WritePostGenerationError(
            "Gemini вернул ошибку сервиса. "
            "Пост не сохранён; попробуйте позже."
        ) from error

    except genai_errors.ServerError as error:
        raise WritePostGenerationError(
            "Gemini вернул ошибку сервиса. "
            "Пост не сохранён; попробуйте позже."
        ) from error

    except genai_errors.APIError as error:
        raise WritePostGenerationError(
            "Не удалось получить ответ Gemini. "
            "Пост не сохранён; попробуйте позже."
        ) from error

    except genai_errors.UnknownApiResponseError as error:
        raise WritePostGenerationError(
            "Не удалось получить ответ Gemini. "
            "Пост не сохранён; попробуйте позже."
        ) from error

    except httpx.RequestError as error:
        raise WritePostGenerationError(
            "Gemini сейчас не отвечает. "
            "Проверьте интернет-соединение "
            "и попробуйте ещё раз."
        ) from error

    output_text = getattr(
        interaction,
        "output_text",
        None,
    )

    if (
        not isinstance(output_text, str)
        or not output_text.strip()
    ):
        raise WritePostGenerationError(
            "Gemini не сформировал текст поста. "
            "Пост не сохранён; попробуйте ещё раз."
        )

    return output_text.strip()
