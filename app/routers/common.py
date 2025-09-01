from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from app.keyboards.menu import main_menu
from app.db import Session
from app.repositories.users import UsersRepo
from aiogram.filters import CommandStart

router = Router(name="common")

@router.message(CommandStart())
async def start(message: Message, roles: set[str]):
    async with Session() as s:
        await UsersRepo(s).upsert_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "Привет! Это бот магазина работ.",
        reply_markup=main_menu(roles)
    )

@router.callback_query(F.data=="menu:main")
async def back_to_menu(cb: CallbackQuery, roles: set[str]):
    await cb.message.edit_text("Главное меню:", reply_markup=main_menu(roles))
    await cb.answer()

router = Router(name="common_cancel")

@router.callback_query(F.data=="fsm:cancel")
async def cancel_fsm(cb: CallbackQuery, state: FSMContext, roles: set[str] | None = None):
    await state.clear()
    await cb.message.edit_text(
        "❌ Действие отменено. Главное меню:",
        reply_markup=main_menu(roles or {"user"})
    )
    await cb.answer()
    
# @router.callback_query()
# async def cb_debug(cb: CallbackQuery):
    # если сюда попали — значит роутеры и диспетчер работают, но конкретный фильтр не совпал
    # await cb.answer(f"callback: {cb.data}", show_alert=False)
