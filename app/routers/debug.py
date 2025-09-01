from aiogram import Router
from aiogram.types import Message, CallbackQuery

debug_router = Router(name="debug")

@debug_router.message()
async def debug_message(msg: Message):
    print(f"[DEBUG] message: {msg.text} from {msg.from_user.id}")

@debug_router.callback_query()
async def debug_callback(cb: CallbackQuery):
    print(f"[DEBUG] callback: {cb.data} from {cb.from_user.id}")
    await cb.answer()
