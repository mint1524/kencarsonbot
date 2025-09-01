from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from app.middlewares.roles import requires

router = Router(name="redactor")

class UploadFSM(StatesGroup):
    course = State()
    name = State()
    description = State()
    prices = State()

@router.callback_query(F.data=="red:upload")
@requires("redactor")
async def start_upload(cb: CallbackQuery, state: FSMContext):
    await state.set_state(UploadFSM.course)
    await cb.message.edit_text("Выбери курс (введи ID курса):")
    await cb.answer()

@router.message(UploadFSM.course)
async def set_course(msg: Message, state: FSMContext):
    await state.update_data(course_id=int(msg.text))
    await state.set_state(UploadFSM.name)
    await msg.answer("Введи название работы:")

@router.message(UploadFSM.name)
async def set_name(msg: Message, state: FSMContext):
    await state.update_data(name=msg.text)
    await state.set_state(UploadFSM.description)
    await msg.answer("Опиши работу (кратко):")

@router.message(UploadFSM.description)
async def set_desc(msg: Message, state: FSMContext):
    await state.update_data(description=msg.text)
    await state.set_state(UploadFSM.prices)
    await msg.answer("Введи цены через пробел: <готовая> <под_ключ>, либо '-' если нет варианта.")

@router.message(UploadFSM.prices)
async def set_prices(msg: Message, state: FSMContext):
    ready_s, key_s = (msg.text.split() + ["", ""])[:2]
    price_ready = None if ready_s=="-" else float(ready_s)
    price_key   = None if key_s=="-" else float(key_s)
    data = await state.get_data()

    # вставка в БД
    from sqlalchemy import text
    from app.db import Session
    async with Session() as s:
        q = text("""
            insert into works(course_id, name, description, status, author)
            values (:c,:n,:d,'not_in_progress',:a) returning id
        """)
        wid = (await s.execute(q, {
            "c": data["course_id"], "n": data["name"], "d": data["description"], "a": msg.from_user.id
        })).scalar_one()
        await s.execute(text("""
            insert into variants(work_id, price_key, price_regular)
            values (:w,:pk,:pr)
        """), {"w": wid, "pk": price_key, "pr": price_ready})
        await s.commit()

    await state.clear()
    await msg.answer(f"Работа добавлена (ID: {wid}). Отправлена на модерацию/установку цен админом при необходимости.")

def wallet_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Вывести средства", callback_data="red:wdr:start")],
        [InlineKeyboardButton(text="Заявки на вывод", callback_data="red:wdr:list")],
    ])

@router.callback_query(F.data=="red:wallet")
@requires("redactor")
async def wallet(cb: CallbackQuery):
    from app.repositories.users import UsersRepo
    async with Session() as s:
        bal = await UsersRepo(s).get_balance(cb.from_user.id)
    await cb.message.edit_text(f"Баланс: {bal:.2f}", reply_markup=wallet_menu())
    await cb.answer()

# ===== Заявка на вывод (упрощённо) =====
from aiogram.fsm.state import StatesGroup, State

class WithdrawFSM(StatesGroup):
    amount = State()
    method = State()
    requisites = State()

@router.callback_query(F.data=="red:wdr:start")
@requires("redactor")
async def wdr_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(WithdrawFSM.amount)
    await cb.message.edit_text("Сколько вывести? (число)")
    await cb.answer()

@router.message(WithdrawFSM.amount)
async def wdr_amount(msg: Message, state: FSMContext):
    amt = float(msg.text)
    await state.update_data(amount=amt)
    await state.set_state(WithdrawFSM.method)
    await msg.answer("Метод: cryptobot / sbp / manual")

@router.message(WithdrawFSM.method)
async def wdr_method(msg: Message, state: FSMContext):
    m = msg.text.strip()
    await state.update_data(method=m)
    await state.set_state(WithdrawFSM.requisites)
    await msg.answer("Реквизиты (TON-кошелёк / телефон СБП / комментарий):")

@router.message(WithdrawFSM.requisites)
async def wdr_finish(msg: Message, state: FSMContext):
    data = await state.get_data()
    async with Session() as s:
        from sqlalchemy import text
        await s.execute(text("""
        insert into withdrawals(user_id, amount, method, requisites, status)
        values (:u, :a, :m, :r::jsonb, 'requested')
        """), {"u": msg.from_user.id, "a": data["amount"], "m": data["method"], "r": {"value": msg.text}})
        await s.commit()
    await state.clear()
    await msg.answer("Заявка создана. Админ проверит и подтвердит выплату.")