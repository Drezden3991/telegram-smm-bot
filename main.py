# Блок 1. Импорт библиотек
import asyncio
import logging
import os
import traceback

from aiogram import Bot, Dispatcher
from aiogram.types import ErrorEvent
from dotenv import load_dotenv

try:
    from aiogram.fsm.storage.redis import RedisStorage
except ModuleNotFoundError:
    RedisStorage = None

from handlers.start import router as start_router
from handlers.clients import router as clients_router
from handlers.post_ideas import router as post_ideas_router
from handlers.write_post import router as write_post_router
from handlers.content_plan import router as content_plan_router

# Блок 2. Подготовка

DEFAULT_LOG_LEVEL = "INFO"
USER_SAFE_ERROR_MESSAGE = (
    "Произошла временная ошибка. Ничего не сохранено — попробуйте ещё раз "
    "или вернитесь назад."
)
logger = logging.getLogger(__name__)


def get_log_level(value: str | None) -> int:
    level_name = (value or DEFAULT_LOG_LEVEL).upper()
    level = logging.getLevelName(level_name)

    return level if isinstance(level, int) else logging.INFO


def configure_logging(log_level: str | None) -> None:
    logging.basicConfig(
        level=get_log_level(log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def safe_traceback(error: Exception) -> str:
    if error.__traceback__ is None:
        return ""

    return "".join(
        f'  File "{frame.filename}", line {frame.lineno}, in {frame.name}\n'
        for frame in traceback.extract_tb(error.__traceback__)
    )


async def handle_unexpected_telegram_error(event: ErrorEvent) -> None:
    error = event.exception
    logger.error(
        "Unhandled Telegram update error type=%s\n%s",
        type(error).__name__,
        safe_traceback(error),
    )

    message = getattr(event.update, "message", None)
    if message is None:
        callback_query = getattr(event.update, "callback_query", None)
        message = getattr(callback_query, "message", None)
    if message is None:
        return

    try:
        await message.answer(USER_SAFE_ERROR_MESSAGE)
    except Exception as delivery_error:
        logger.error(
            "Could not deliver safe error message type=%s",
            type(delivery_error).__name__,
        )

# Блок 3. Создание объектов

# Блок 4. Подключение обработчиков


# Блок 5. Запуск бота
def create_fsm_storage(redis_url: str):
    if not redis_url:
        raise RuntimeError(
            "FSM_REDIS_URL is required for persistent FSM storage."
        )

    if RedisStorage is None:
        raise RuntimeError(
            "Persistent FSM requires the redis dependency. "
            "Install the pinned project dependencies."
        )

    return RedisStorage.from_url(redis_url)


async def create_dispatcher(redis_url: str) -> Dispatcher:
    storage = create_fsm_storage(redis_url)

    try:
        await storage.redis.ping()
    except Exception as error:
        await storage.close()
        raise RuntimeError(
            "Persistent FSM Redis backend is unavailable."
        ) from error

    logger.info("Persistent FSM Redis backend is ready")

    dispatcher = Dispatcher(
        storage=storage,
        events_isolation=storage.create_isolation(),
    )
    dispatcher.include_router(start_router)
    dispatcher.include_router(post_ideas_router)
    dispatcher.include_router(write_post_router)
    dispatcher.include_router(content_plan_router)
    dispatcher.include_router(clients_router)
    dispatcher.errors.register(handle_unexpected_telegram_error)
    dispatcher.shutdown.register(log_application_shutdown)

    return dispatcher


async def log_application_shutdown(*args, **kwargs) -> None:
    logger.info("Application shutdown completed")


async def main():
    load_dotenv()
    configure_logging(os.getenv("LOG_LEVEL"))
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    redis_url = os.getenv("FSM_REDIS_URL")

    if not telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required.")

    dispatcher = await create_dispatcher(redis_url)
    bot = Bot(token=telegram_bot_token)
    logger.info("Application started")
    logger.info("Polling started")
    await dispatcher.start_polling(bot)


async def run_application():
    try:
        await main()
    except Exception as error:
        logger.error(
            "Application stopped by critical error type=%s\n%s",
            type(error).__name__,
            safe_traceback(error),
        )
        raise


if __name__ == "__main__":
    asyncio.run(run_application())
