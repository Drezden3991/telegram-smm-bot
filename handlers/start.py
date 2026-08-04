from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

router = Router()

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👥 Клиенты")],
        [KeyboardButton(text="💡 Идея постов")],
        [KeyboardButton(text="✍️ Написать пост")],
        [KeyboardButton(text="📅 Контент-план")],
    ],
    resize_keyboard=True,
)


@router.message(CommandStart())
async def start(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    await message.answer(
        "Привет! Я SMM MVP Bot. Чем могу помочь?",
        reply_markup=main_menu
    )
