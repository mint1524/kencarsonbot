from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, PreCheckoutQuery
from sqlalchemy import text
from app.keyboards.shop import shop_list_kb, variant_buy_kb
from app.db import Session
from app.services.shop import ShopService
from app.config import settings
from app.keyboards.nav import back_to_menu_kb, with_back

# --------- РОУТЕР ДЛЯ ПОКУПАТЕЛЯ (витрина, crypto) ----------
user_router = Router(name="user")

def buy_keyboard(pay_url: str, invoice_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оплатить", url=pay_url)],
        [InlineKeyboardButton(text="Проверить оплату", callback_data=f"pay:check:{invoice_id}")],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="menu:main")],
    ])

@user_router.callback_query(F.data == "user:shop")
async def shop_entry(cb: CallbackQuery):
    await shop_page(cb, 0)

PAGE_SIZE = 8

@user_router.callback_query(F.data == "user:orders")
async def user_orders(cb: CallbackQuery):
    # Заглушка: сюда выведешь список покупок пользователя
    await cb.message.edit_text("📦 Мои покупки (скоро будет список).", reply_markup=back_to_menu_kb())
    await cb.answer()

@user_router.callback_query(F.data.regexp(r"^user:shop:list:(\d)$"))
async def shop_list(cb: CallbackQuery):
    page = int(cb.data.rsplit(":",1)[1])
    await shop_page(cb, page)

async def shop_page(cb: CallbackQuery, page: int):
    off = page * PAGE_SIZE
    async with Session() as s:
        rows = (await s.execute(text("""
          select w.id, w.name, c.name as course_name, v.id as variant_id, 
                 v.price_regular, v.price_key
          from works w
          join variants v on v.work_id = w.id
          join courses c on c.id = w.course_id
          where w.status = 'ready'
          order by w.updated_at desc
          limit :lim offset :off
        """), {"lim": PAGE_SIZE, "off": off})).mappings().all()
        total = (await s.execute(text("select count(*) from works where status='ready'"))).scalar_one()
    if not rows:
        await cb.message.edit_text("Нет готовых работ.")
        return await cb.answer()

    lines = []
    for r in rows:
        lines.append(
            f"#{r['id']} • {r['course_name']} — {r['name']}  "
            f"[Готовая: {r['price_regular'] or '—'} | Под ключ: {r['price_key'] or '—'}]\n"
            f"/open_{r['variant_id']}"
        )
    text_out = "Доступные работы:\n\n" + "\n".join(lines)
    has_next = (off + PAGE_SIZE) < total
    await cb.message.edit_text(text_out, reply_markup=shop_list_kb(page, page>0, has_next))
    await cb.answer()

@user_router.message(F.text.regexp(r"^/open_(\d+)$"))
async def open_variant(msg: Message):
    var_id = int(msg.text.split("_")[1])
    async with Session() as s:
        r = (await s.execute(text("""
          select v.id, v.price_regular, v.price_key, w.name, c.name as course_name
          from variants v 
          join works w on w.id = v.work_id
          join courses c on c.id = w.course_id
          where v.id = :v
        """), {"v": var_id})).mappings().one()
    txt = (f"Вариант #{r['id']} • {r['course_name']} — {r['name']}\n"
           f"Готовая: {r['price_regular'] or '—'} | Под ключ: {r['price_key'] or '—'}")
    kb = variant_buy_kb(var_id, r["price_regular"] is not None, r["price_key"] is not None)
    await msg.answer(txt, reply_markup=with_back(kb))

# покупки через CRYPTO
@user_router.callback_query(F.data.regexp(r"^user:buy:(ready|key):(\d+)$"))
async def buy_by_button(cb: CallbackQuery):
    kind, var_id = cb.data.split(":")[2], int(cb.data.split(":")[3])
    async with Session() as s:
        svc = ShopService(s)
        pid, pay_url, invoice_id, price = await svc.create_purchase_with_invoice(
            buyer_id=cb.from_user.id, variant_id=var_id, kind=kind, currency="USDT"
        )
    await cb.message.edit_text(
        f"Счёт на {price} ({'готовая' if kind=='ready' else 'под ключ'}). "
        f"Оплатите и нажмите «Проверить оплату».",
        reply_markup=buy_keyboard(pay_url, invoice_id)
    )
    await cb.answer()

@user_router.callback_query(F.data.startswith("pay:check:"))
async def pay_check(cb: CallbackQuery, bot):
    invoice_id = int(cb.data.split(":")[2])
    async with Session() as s:
        ok, status, info = await ShopService(s).check_and_settle(invoice_id)

    if not ok:
        await cb.message.edit_text(f"Статус счёта: {status}", reply_markup=back_to_menu_kb())
        return await cb.answer()

    # оплачен
    if info and info["kind"] == "ready":
        # пытаемся выдать файл сразу
        async with Session() as s:
            svc = ShopService(s)
            asset = await svc.get_ready_asset_for_variant(info["variant_id"])
        if asset:
            await bot.send_document(info["buyer_id"], asset["tg_file_id"], caption=asset.get("file_name") or "Спасибо за покупку!")
            await cb.message.edit_text("✅ Оплачено! Файл отправлен вам в личные сообщения.", reply_markup=back_to_menu_kb())
        else:
            await cb.message.edit_text("✅ Оплачено! Но файл пока не прикреплён. Мы пришлём его позже.", reply_markup=back_to_menu_kb())
    else:
        # под ключ — работа ушла в пул
        await cb.message.edit_text("✅ Оплачено! Работа принята в выполнение. Когда будет готово — пришлём файл.", reply_markup=back_to_menu_kb())
    await cb.answer()


# --------- РОУТЕР ДЛЯ TELEGRAM PAYMENTS (RUB) ----------
tgpay_router = Router(name="user_tgpay")

@tgpay_router.callback_query(F.data.regexp(r"^user:buy_tg:(ready|key):(\d+)$"))
async def buy_tg(cb: CallbackQuery, bot):
    kind, variant_id = cb.data.split(":")[2], int(cb.data.split(":")[3])
    async with Session() as s:
        svc = ShopService(s)
        try:
            await svc.create_purchase_tg_invoice(
                bot=bot,
                chat_id=cb.message.chat.id,
                buyer_id=cb.from_user.id,
                variant_id=variant_id,
                kind=kind
            )
        except ValueError as e:
            await cb.answer(str(e), show_alert=True); return
    await cb.answer()

@tgpay_router.pre_checkout_query()
async def on_pre_checkout(pcq: PreCheckoutQuery, bot):
    await bot.answer_pre_checkout_query(pcq.id, ok=True)

@tgpay_router.message(F.successful_payment)
async def on_success_payment(msg: Message, bot):
    purchase_id = msg.successful_payment.invoice_payload
    tg_charge = msg.successful_payment.telegram_payment_charge_id
    provider_charge = msg.successful_payment.provider_payment_charge_id
    amount_rub = msg.successful_payment.total_amount / 100

    async with Session() as s:
        # помечаем payment
        await s.execute(text("""
          update payments set status='paid', telegram_charge_id=:tgc, provider_payment_charge_id=:pcg,
                 currency='RUB', amount=:amt, updated_at=now()
           where purchase_id=:pid::uuid and provider='telegram'
        """), {"tgc": tg_charge, "pcg": provider_charge, "amt": amount_rub, "pid": purchase_id})

        # читаем покупку
        br = (await s.execute(text("""
            select p.buyer_id, p.variant_id, p.kind, p.status
              from purchases p where p.id=:id::uuid for update
        """), {"id": purchase_id})).first()
        if not br:
            return await msg.answer("⚠️ Покупка не найдена.")
        buyer_id, variant_id, kind, pstatus = br

        # автор
        author_id = (await s.execute(text("""
            select w.author from variants v join works w on w.id = v.work_id
             where v.id = :v
        """), {"v": variant_id})).scalar_one()

        # статус покупки
        new_status = "paid" if kind == "ready" else "in_progress"
        await s.execute(text("""
          update purchases set price=:p, status=:st, updated_at=now() where id=:id::uuid
        """), {"p": amount_rub, "st": new_status, "id": purchase_id})

        # 70/30
        author_share = 0.0 if buyer_id == author_id else round(float(amount_rub) * 0.70, 2)
        platform_share = round(float(amount_rub) - author_share, 2)
        await s.execute(text("update users set balance = balance + :x where tg_id=:u"),
                        {"x": author_share, "u": author_id})
        await s.execute(text("update users set balance = balance + :x where tg_id=:u"),
                        {"x": platform_share, "u": settings.PLATFORM_USER_ID})

        # если под ключ — отметим работу «в процессе»
        if kind == "key":
            await s.execute(text("""
              update works set status='in_progress', updated_at=now()
               where id = (select work_id from variants where id=:v)
            """), {"v": variant_id})

        await s.commit()

    # выдача файла при "готовой"
    if kind == "ready":
        async with Session() as s:
            svc = ShopService(s)
            asset = await svc.get_ready_asset_for_variant(variant_id)
        if asset:
            await bot.send_document(buyer_id, asset["tg_file_id"], caption=asset.get("file_name") or "Спасибо за покупку!")
            await msg.answer("✅ Оплата получена. Файл отправлен вам в личные сообщения.")
        else:
            await msg.answer("✅ Оплата получена. Файл ещё не прикреплён, мы пришлём его позже.")
    else:
        await msg.answer("✅ Оплата получена. Работа принята в выполнение.")
