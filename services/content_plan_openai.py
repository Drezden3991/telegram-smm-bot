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

from models.content_plan import SevenDayContentPlan
from services.content_plan import (
    CONTENT_PLAN_AI_CONTRACT,
    ContentPlanGenerationError,
)


OPENAI_MODEL = "gpt-5.6"
OPENAI_REASONING_EFFORT: ReasoningEffort = "low"
OPENAI_TIMEOUT_SECONDS = 45.0


def generate_ai_content_plan(brief):
    try:
        client = OpenAI(
            timeout=OPENAI_TIMEOUT_SECONDS,
            max_retries=1,
        )

        response_input: ResponseInputParam = [
            EasyInputMessageParam(
                role="developer",
                content=CONTENT_PLAN_AI_CONTRACT,
            ),
            EasyInputMessageParam(
                role="user",
                content=(
                    "Краткий бриф пользователя:\n"
                    f"{brief}"
                ),
            ),
        ]

        response = client.responses.parse(
            model=OPENAI_MODEL,
            reasoning=Reasoning(
                effort=OPENAI_REASONING_EFFORT,
            ),
            input=response_input,
            text_format=SevenDayContentPlan,
        )

    except AuthenticationError as error:
        raise ContentPlanGenerationError(
            "Не удалось авторизоваться в OpenAI. "
            "Проверьте настройку API и повторите позже."
        ) from error

    except RateLimitError as error:
        raise ContentPlanGenerationError(
            "OpenAI временно ограничил число запросов. "
            "Попробуйте ещё раз немного позже."
        ) from error

    except (
        APITimeoutError,
        APIConnectionError,
    ) as error:
        raise ContentPlanGenerationError(
            "OpenAI сейчас не отвечает. "
            "Проверьте интернет-соединение "
            "и попробуйте ещё раз."
        ) from error

    except APIStatusError as error:
        raise ContentPlanGenerationError(
            "OpenAI вернул ошибку сервиса. "
            "Контент-план не сохранён; "
            "попробуйте позже."
        ) from error

    except OpenAIError as error:
        raise ContentPlanGenerationError(
            "Не удалось получить ответ OpenAI. "
            "Контент-план не сохранён; "
            "попробуйте позже."
        ) from error

    except (
        ValidationError,
        ValueError,
    ) as error:
        raise ContentPlanGenerationError(
            "OpenAI вернул неполный контент-план. "
            "Ничего не сохранено; "
            "попробуйте ещё раз."
        ) from error

    content_plan = response.output_parsed

    if content_plan is None:
        raise ContentPlanGenerationError(
            "OpenAI не сформировал контент-план. "
            "Ничего не сохранено; "
            "попробуйте ещё раз."
        )

    days = [
        item.day
        for item in content_plan.days
    ]

    if days != list(range(1, 8)):
        raise ContentPlanGenerationError(
            "OpenAI вернул дни в неверном порядке. "
            "Ничего не сохранено; "
            "попробуйте ещё раз."
        )

    return content_plan
