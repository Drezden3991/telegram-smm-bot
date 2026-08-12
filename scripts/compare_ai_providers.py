"""Developer-only smoke-test harness for manual AI provider comparison."""

import argparse
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services import content_plan as content_plan_service
from services import content_plan_gemini as content_plan_gemini_service
from services import content_plan_groq as content_plan_groq_service
from services import content_plan_openai as content_plan_openai_service
from services import post_ideas as post_ideas_service
from services import post_ideas_gemini as post_ideas_gemini_service
from services import post_ideas_groq as post_ideas_groq_service
from services import write_post as write_post_service
from services import write_post_gemini as write_post_gemini_service
from services import write_post_groq as write_post_groq_service


TEST_CLIENT = {
    "name": "Coffee Lab Tallinn",
    "last_name": "",
    "instagram": "@coffeelab_test",
    "notes": (
        "Небольшая современная кофейня в Таллинне; аудитория 20–35 лет; "
        "акцент на specialty coffee, уюте и работе с ноутбуком."
    ),
}

CONTENT_PLAN_BRIEF = (
    "Привлечь новых посетителей и познакомить аудиторию с кофейней."
)
CONTENT_PLAN_SELECTED_IDEAS = [
    "Знакомство со specialty coffee",
    "Кофейня как место для работы с ноутбуком",
]
WRITE_POST_TOPIC = "Почему specialty coffee стоит попробовать"
WRITE_POST_STYLE = "Дружелюбный"
POST_IDEAS_BRIEF = "Идеи для знакомства новой аудитории с кофейней"
POST_IDEAS_EXISTING = [
    "Как выбрать кофе под настроение",
    "Что такое specialty coffee",
    "Кофейня как место для работы с ноутбуком",
]


@dataclass
class ProviderRunResult:
    provider: str
    status: str
    elapsed_seconds: float | None = None
    result: object | None = None
    error: str | None = None


def _provider_specs(mode: str):
    if mode == "content_plan":
        brief = content_plan_service.build_ai_brief(
            TEST_CLIENT,
            CONTENT_PLAN_SELECTED_IDEAS,
            CONTENT_PLAN_BRIEF,
        )
        return {
            "openai": (
                "OPENAI_API_KEY",
                content_plan_openai_service.generate_ai_content_plan,
                (brief,),
            ),
            "gemini": (
                "GEMINI_API_KEY",
                content_plan_gemini_service.generate_gemini_content_plan,
                (brief,),
            ),
            "groq": (
                "GROQ_API_KEY",
                content_plan_groq_service.generate_groq_content_plan,
                (brief,),
            ),
        }

    if mode == "write_post":
        client_context = write_post_service.build_client_ai_context(
            TEST_CLIENT
        )
        arguments = (
            client_context,
            WRITE_POST_TOPIC,
            WRITE_POST_STYLE,
        )
        return {
            "gemini": (
                "GEMINI_API_KEY",
                write_post_gemini_service.generate_gemini_post,
                arguments,
            ),
            "groq": (
                "GROQ_API_KEY",
                write_post_groq_service.generate_groq_post,
                arguments,
            ),
        }

    if mode == "post_ideas":
        client_context = post_ideas_service.build_client_ai_context(
            TEST_CLIENT
        )
        arguments = (
            client_context,
            POST_IDEAS_BRIEF,
            POST_IDEAS_EXISTING,
        )
        return {
            "gemini": (
                "GEMINI_API_KEY",
                post_ideas_gemini_service.generate_gemini_post_ideas,
                arguments,
            ),
            "groq": (
                "GROQ_API_KEY",
                post_ideas_groq_service.generate_groq_post_ideas,
                arguments,
            ),
        }

    raise ValueError(f"Неизвестный режим сравнения: {mode}")


def _safe_error_message(error: Exception) -> str:
    expected_errors = (
        content_plan_service.ContentPlanGenerationError,
        write_post_service.WritePostGenerationError,
        post_ideas_service.PostIdeasGenerationError,
    )

    if isinstance(error, expected_errors):
        return str(error)

    return f"Непредвиденная ошибка: {type(error).__name__}"


def format_result(result: object) -> str:
    if isinstance(result, str):
        return result

    if isinstance(result, list):
        return "\n".join(
            f"{number}. {item}"
            for number, item in enumerate(result, start=1)
        )

    if hasattr(result, "model_dump_json"):
        return result.model_dump_json(indent=2)

    return str(result)


def run_provider(
    provider: str,
    key_name: str,
    generator,
    arguments: tuple,
) -> ProviderRunResult:
    if not os.getenv(key_name):
        return ProviderRunResult(
            provider=provider,
            status="SKIPPED",
            error=f"{key_name} not configured",
        )

    started_at = time.perf_counter()

    try:
        result = generator(*arguments)

    except Exception as error:
        return ProviderRunResult(
            provider=provider,
            status="ERROR",
            elapsed_seconds=time.perf_counter() - started_at,
            error=_safe_error_message(error),
        )

    return ProviderRunResult(
        provider=provider,
        status="OK",
        elapsed_seconds=time.perf_counter() - started_at,
        result=result,
    )


def print_provider_result(result: ProviderRunResult) -> None:
    print(f"--- {result.provider.title()} ---")
    print(f"Status: {result.status}")

    if result.elapsed_seconds is not None:
        print(f"Time: {result.elapsed_seconds:.2f}s")

    if result.status == "OK":
        print("Result:")
        print(format_result(result.result))
    elif result.error:
        print(f"Error: {result.error}")

    print()


def run_comparison(
    mode: str,
    providers: list[str] | None = None,
) -> list[ProviderRunResult]:
    specs = _provider_specs(mode)
    selected_providers = providers or list(specs)
    unknown_providers = [
        provider
        for provider in selected_providers
        if provider not in specs
    ]

    if unknown_providers:
        raise ValueError(
            "Недоступные providers для "
            f"{mode}: {', '.join(unknown_providers)}"
        )

    print(f"=== {mode.upper()} ===\n")
    results = []

    for provider in selected_providers:
        key_name, generator, arguments = specs[provider]
        result = run_provider(
            provider,
            key_name,
            generator,
            arguments,
        )
        results.append(result)
        print_provider_result(result)

    return results


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ручное сравнение AI providers для SMM Bot.",
    )
    parser.add_argument(
        "mode",
        choices=("content_plan", "write_post", "post_ideas"),
        help="Сценарий сравнения.",
    )
    parser.add_argument(
        "--providers",
        nargs="+",
        help="Необязательный список providers для запуска.",
    )

    return parser.parse_args()


def main() -> None:
    load_dotenv()
    arguments = parse_arguments()
    run_comparison(arguments.mode, arguments.providers)


if __name__ == "__main__":
    main()
