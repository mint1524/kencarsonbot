from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from app.keyboards.menu import main_menu
from app.db import Session
from app.repositories.users import UsersRepo

router = Router(name="common")

@router.message(F.text=="/start")
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
