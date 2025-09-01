from aiogram import Router, F
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import text
from app.db import Session
from app.services.shop import ShopService
from app.keyboards.nav import nav

router = Router(name="user_key")

class KeyFSM(StatesGroup):
    var = State()
    deadline = State()
    comment = State()

@router.callback_query(F.data.regexp(r"^user:key:start:(\d+)$"))
async def key_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(KeyFSM.var)
    await state.update_data(var=int(cb.data.split(":")[3]))
    await state.set_state(KeyFSM.deadline)
    await cb.message.edit_text("Укажи дедлайн (например 2025-09-15 18:00):", reply_markup=nav(cancel="menu:main"))

@router.message(KeyFSM.deadline)
async def key_deadline(msg: Message, state: FSMContext):
    await state.update_data(deadline=msg.text.strip())
    await state.set_state(KeyFSM.comment)
    await msg.answer("Краткое ТЗ/пожелания (одним сообщением):", reply_markup=nav(cancel="menu:main"))

@router.message(KeyFSM.comment)
async def key_finish(msg: Message, state: FSMContext):
    data = await state.get_data()
    async with Session() as s:
        svc = ShopService(s)
        # создаём инвойс через существующий сервис (без правки сервиса)
        purchase_id, pay_url, invoice_id, price = await svc.create_purchase_with_invoice(
            buyer_id=msg.from_user.id, variant_id=data["var"], kind="key", currency="USDT"
        )
        # доклеиваем дедлайн и комментарий
        await s.execute(text("update purchases set deadline_at=:d, client_comment=:c where id=:p::uuid"),
                        {"d": data["deadline"], "c": msg.text.strip(), "p": purchase_id})
        await s.commit()
    await state.clear()
    await msg.answer(f"Счёт на {price}. Оплатите и нажмите «Проверить оплату».",
                     reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                         [InlineKeyboardButton(text="Оплатить", url=pay_url)],
                         [InlineKeyboardButton(text="Проверить оплату", callback_data=f"pay:check:{invoice_id}")]
                     ]))
