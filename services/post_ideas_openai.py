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
from pydantic import ValidationError

from models.post_idea import GeneratedPostIdeas
from services.post_ideas import (
    POST_IDEAS_AI_CONTRACT,
    PostIdeasGenerationError,
    format_existing_post_ideas,
)


OPENAI_MODEL = "gpt-5.6"
OPENAI_REASONING_EFFORT: ReasoningEffort = "low"
OPENAI_TIMEOUT_SECONDS = 45.0


def generate_openai_post_ideas(
    client_ai_context: str,
    brief: str,
    existing_ideas: list[str],
) -> GeneratedPostIdeas:
    client_context_text = (
        client_ai_context
        if client_ai_context
        else "Не указан."
    )
    existing_ideas_text = format_existing_post_ideas(
        existing_ideas
    )

    try:
        client = OpenAI(
            timeout=OPENAI_TIMEOUT_SECONDS,
            max_retries=1,
        )

        response_input: ResponseInputParam = [
            EasyInputMessageParam(
                role="developer",
                content=POST_IDEAS_AI_CONTRACT,
            ),
            EasyInputMessageParam(
                role="user",
                content=(
                    "Контекст клиента:\n"
                    f"{client_context_text}\n\n"
                    "Бриф или тема пользователя:\n"
                    f"{brief}\n\n"
                    "Существующие идеи, которые не нужно повторять:\n"
                    f"{existing_ideas_text}"
                ),
            ),
        ]

        response = client.responses.parse(
            model=OPENAI_MODEL,
            reasoning=Reasoning(
                effort=OPENAI_REASONING_EFFORT,
            ),
            input=response_input,
            text_format=GeneratedPostIdeas,
        )

    except AuthenticationError as error:
        raise PostIdeasGenerationError(
            "Не удалось авторизоваться в OpenAI. "
            "Проверьте настройку API и повторите позже."
        ) from error

    except RateLimitError as error:
        raise PostIdeasGenerationError(
            "OpenAI временно ограничил число запросов. "
            "Попробуйте ещё раз немного позже."
        ) from error

    except (
        APITimeoutError,
        APIConnectionError,
    ) as error:
        raise PostIdeasGenerationError(
            "OpenAI сейчас не отвечает. "
            "Проверьте интернет-соединение "
            "и попробуйте ещё раз."
        ) from error

    except APIStatusError as error:
        raise PostIdeasGenerationError(
            "OpenAI вернул ошибку сервиса. "
            "Идеи не созданы; попробуйте позже."
        ) from error

    except OpenAIError as error:
        raise PostIdeasGenerationError(
            "Не удалось получить ответ OpenAI. "
            "Идеи не созданы; попробуйте позже."
        ) from error

    except (
        ValidationError,
        ValueError,
    ) as error:
        raise PostIdeasGenerationError(
            "OpenAI вернул некорректный список идей. "
            "Ничего не сохранено; попробуйте ещё раз."
        ) from error

    generated_ideas = response.output_parsed

    if generated_ideas is None:
        raise PostIdeasGenerationError(
            "OpenAI не сформировал идеи постов. "
            "Ничего не сохранено; попробуйте ещё раз."
        )

    if (
        len(generated_ideas.ideas) != 3
        or any(not idea for idea in generated_ideas.ideas)
    ):
        raise PostIdeasGenerationError(
            "OpenAI вернул некорректный список идей. "
            "Ничего не сохранено; попробуйте ещё раз."
        )

    return generated_ideas