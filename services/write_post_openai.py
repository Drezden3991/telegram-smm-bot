from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)
from openai.types.responses import (
    EasyInputMessageParam,
    ResponseInputParam,
)
from openai.types.shared.reasoning_effort import ReasoningEffort
from openai.types.shared_params.reasoning import Reasoning

from services.write_post import (
    WRITE_POST_AI_CONTRACT,
    WritePostGenerationError,
)


OPENAI_MODEL = "gpt-5.6"
OPENAI_REASONING_EFFORT: ReasoningEffort = "low"
OPENAI_TIMEOUT_SECONDS = 45.0


def generate_openai_post(
    client_ai_context: str,
    topic: str,
    style: str,
) -> str:
    client_context_text = (
        client_ai_context
        if client_ai_context
        else "Не указан."
    )

    try:
        client = OpenAI(
            timeout=OPENAI_TIMEOUT_SECONDS,
            max_retries=1,
        )

        response_input: ResponseInputParam = [
            EasyInputMessageParam(
                role="developer",
                content=WRITE_POST_AI_CONTRACT,
            ),
            EasyInputMessageParam(
                role="user",
                content=(
                    "Контекст клиента:\n"
                    f"{client_context_text}\n\n"
                    "Тема поста:\n"
                    f"{topic}\n\n"
                    "Стиль поста:\n"
                    f"{style}"
                ),
            ),
        ]

        response = client.responses.create(
            model=OPENAI_MODEL,
            reasoning=Reasoning(
                effort=OPENAI_REASONING_EFFORT,
            ),
            input=response_input,
        )

    except AuthenticationError as error:
        raise WritePostGenerationError(
            "Не удалось авторизоваться в OpenAI. "
            "Проверьте настройку API и повторите позже."
        ) from error

    except RateLimitError as error:
        raise WritePostGenerationError(
            "OpenAI временно ограничил число запросов. "
            "Попробуйте ещё раз немного позже."
        ) from error

    except (
        APITimeoutError,
        APIConnectionError,
    ) as error:
        raise WritePostGenerationError(
            "OpenAI сейчас не отвечает. "
            "Проверьте интернет-соединение "
            "и попробуйте ещё раз."
        ) from error

    except APIStatusError as error:
        raise WritePostGenerationError(
            "OpenAI вернул ошибку сервиса. "
            "Пост не сохранён; попробуйте позже."
        ) from error

    except OpenAIError as error:
        raise WritePostGenerationError(
            "Не удалось получить ответ OpenAI. "
            "Пост не сохранён; попробуйте позже."
        ) from error

    output_text = response.output_text

    if (
        not isinstance(output_text, str)
        or not output_text.strip()
    ):
        raise WritePostGenerationError(
            "OpenAI не сформировал текст поста. "
            "Пост не сохранён; попробуйте ещё раз."
        )

    return output_text.strip()