# Блок 1. Импорт библиотек
import asyncio
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from handlers.start import router as start_router
from handlers.clients import router as clients_router
from handlers.post_ideas import router as post_ideas_router
from handlers.write_post import router as write_post_router
from handlers.content_plan import router as content_plan_router

# Блок 2. Подготовка
load_dotenv()
telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")

# Блок 3. Создание объектов
bot = Bot(token=telegram_bot_token)
dp = Dispatcher()

# Блок 4. Подключение обработчиков
dp.include_router(start_router)

dp.include_router(post_ideas_router)
dp.include_router(write_post_router)
dp.include_router(content_plan_router)
dp.include_router(clients_router)

# Блок 5. Запуск бота
async def main():
    print("Бот успешно запущен")
    await dp.start_polling(bot)


asyncio.run(main())
