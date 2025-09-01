from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from sqlalchemy import text

from app.middlewares.roles import Requires, MissingRole
from app.db import Session
from app.keyboards.nav import back_to_menu_kb
from app.keyboards.menu import main_menu

router = Router(name="redactor")

# ---------- FSM загрузки работы ----------
class UploadFSM(StatesGroup):
    course = State()
    name = State()
    description = State()
    prices = State()

def cancel_hint() -> str:
    return "\n\nОтмена: /cancel"

@router.message(F.text == "/cancel")
async def cancel_any(msg: Message, state: FSMContext, roles: set[str] | None = None):
    await state.clear()
    await msg.answer("Отменено. Главное меню:", reply_markup=main_menu(roles or {"user"}))

# Гейт на «нет прав» (чтобы не спамило по 10 раз)
@router.callback_query(MissingRole("redactor"), F.data.regexp(r"^red:"))
async def red_gate(cb: CallbackQuery):
    await cb.answer("Недостаточно прав.", show_alert=True)

@router.callback_query(Requires("redactor"), F.data == "red:upload")
async def start_upload(cb: CallbackQuery, state: FSMContext):
    await state.set_state(UploadFSM.course)
    await cb.message.edit_text(
        "Выбери курс (введи **ID курса**)."
        "\nНапример: `1`"
        f"{cancel_hint()}",
        parse_mode="Markdown",
        reply_markup=back_to_menu_kb()
    )
    await cb.answer()

@router.message(UploadFSM.course)
async def set_course(msg: Message, state: FSMContext):
    txt = (msg.text or "").strip()
    if not txt.isdigit():
        return await msg.answer("Нужно число (ID курса). Попробуй ещё раз.\nНапример: `1`" + cancel_hint(),
                                parse_mode="Markdown")
    course_id = int(txt)
    # проверим, что курс существует
    async with Session() as s:
        exists = (await s.execute(text("select 1 from courses where id=:c"), {"c": course_id})).first()
    if not exists:
        return await msg.answer(f"Курс с ID `{course_id}` не найден. Введи существующий ID." + cancel_hint(),
                                parse_mode="Markdown")

    await state.update_data(course_id=course_id)
    await state.set_state(UploadFSM.name)
    await msg.answer("Введи **название** работы:" + cancel_hint(), parse_mode="Markdown")

@router.message(UploadFSM.name)
async def set_name(msg: Message, state: FSMContext):
    name = (msg.text or "").strip()
    if not name:
        return await msg.answer("Название не может быть пустым. Введи ещё раз." + cancel_hint())
    await state.update_data(name=name)
    await state.set_state(UploadFSM.description)
    await msg.answer("Опиши работу (кратко):" + cancel_hint())

@router.message(UploadFSM.description)
async def set_desc(msg: Message, state: FSMContext):
    desc = (msg.text or "").strip()
    await state.update_data(description=desc)
    await state.set_state(UploadFSM.prices)
    await msg.answer(
        "Введи цены через пробел: `<готовая> <под_ключ>`.\n"
        "Если варианта нет — поставь `-`.\n"
        "Примеры:\n"
        "• `1990 4990`\n"
        "• `- 4990`\n"
        "• `1990 -`\n" + cancel_hint(),
        parse_mode="Markdown"
    )

def _parse_price(token: str | None):
    token = (token or "").strip()
    if token in {"", "-"}:
        return None
    try:
        return float(token.replace(",", "."))
    except ValueError:
        return "bad"  # маркер невалидного ввода

@router.message(UploadFSM.prices)
async def set_prices(msg: Message, state: FSMContext):
    parts = (msg.text or "").split()
    ready_s = parts[0] if len(parts) > 0 else ""
    key_s   = parts[1] if len(parts) > 1 else ""

    price_ready = _parse_price(ready_s)
    price_key   = _parse_price(key_s)
    if price_ready == "bad" or price_key == "bad":
        return await msg.answer("Неверный формат. Пример: `1990 4990` или `- 4990`." + cancel_hint(),
                                parse_mode="Markdown")

    data = await state.get_data()
    async with Session() as s:
        # ещё раз перестрахуемся, что курс жив
        exists = (await s.execute(text("select 1 from courses where id=:c"), {"c": data["course_id"]})).first()
        if not exists:
            return await msg.answer(f"Курс с ID `{data['course_id']}` не найден. Введите корректный ID." + cancel_hint(),
                                    parse_mode="Markdown")

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
    await msg.answer(
        f"✅ Работа добавлена (ID: {wid}). Отправлена на модерацию/установку цен админом при необходимости.",
        reply_markup=back_to_menu_kb()
    )

def wallet_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Вывести средства", callback_data="red:wdr:start")],
        [InlineKeyboardButton(text="Заявки на вывод", callback_data="red:wdr:list")],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="menu:main")],
    ])

@router.callback_query(Requires("redactor"), F.data=="red:wallet")
async def wallet(cb: CallbackQuery):
    from app.repositories.users import UsersRepo
    async with Session() as s:
        bal = await UsersRepo(s).get_balance(cb.from_user.id)
    await cb.message.edit_text(f"Баланс: {bal:.2f}", reply_markup=wallet_menu())
    await cb.answer()

# ====== Вывод средств (упрощённо) ======
class WithdrawFSM(StatesGroup):
    amount = State()
    method = State()
    requisites = State()

@router.callback_query(Requires("redactor"), F.data=="red:wdr:start")
async def wdr_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(WithdrawFSM.amount)
    await cb.message.edit_text("Сколько вывести? (число)" + cancel_hint(), reply_markup=back_to_menu_kb())
    await cb.answer()

@router.message(WithdrawFSM.amount)
async def wdr_amount(msg: Message, state: FSMContext):
    try:
        amt = float((msg.text or "").replace(",", "."))
    except ValueError:
        return await msg.answer("Нужно число, попробуй ещё раз." + cancel_hint())
    await state.update_data(amount=amt)
    await state.set_state(WithdrawFSM.method)
    await msg.answer("Метод: `cryptobot` / `sbp` / `manual`" + cancel_hint(), parse_mode="Markdown")

@router.message(WithdrawFSM.method)
async def wdr_method(msg: Message, state: FSMContext):
    m = (msg.text or "").strip().lower()
    if m not in {"cryptobot", "sbp", "manual"}:
        return await msg.answer("Метод должен быть: `cryptobot` / `sbp` / `manual`." + cancel_hint(),
                                parse_mode="Markdown")
    await state.update_data(method=m)
    await state.set_state(WithdrawFSM.requisites)
    await msg.answer("Реквизиты (TON-кошелёк / телефон СБП / комментарий):" + cancel_hint())

@router.message(WithdrawFSM.requisites)
async def wdr_finish(msg: Message, state: FSMContext):
    data = await state.get_data()
    async with Session() as s:
        await s.execute(text("""
        insert into withdrawals(user_id, amount, method, requisites, status)
        values (:u, :a, :m, :r::jsonb, 'requested')
        """), {"u": msg.from_user.id, "a": data["amount"], "m": data["method"], "r": {"value": msg.text}})
        await s.commit()
    await state.clear()
    await msg.answer("✅ Заявка создана. Админ проверит и подтвердит выплату.", reply_markup=back_to_menu_kb())

@router.callback_query(Requires("redactor"), F.data=="red:works")
async def list_my_works(cb: CallbackQuery):
    async with Session() as s:
        rows = (await s.execute(text("""
          select w.id, w.name, w.status, c.name as course_name
          from works w
          join courses c on c.id = w.course_id
          where w.author = :u
          order by w.updated_at desc limit 20
        """), {"u": cb.from_user.id})).mappings().all()
    if not rows:
        await cb.message.edit_text("У тебя пока нет работ.", reply_markup=back_to_menu_kb())
    else:
        text_out = "Твои работы:\n\n" + "\n".join(
            f"#{r['id']} • {r['course_name']} — {r['name']} • {r['status']}" for r in rows
        )
        await cb.message.edit_text(text_out, reply_markup=back_to_menu_kb())
    await cb.answer()
