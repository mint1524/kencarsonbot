from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import text
from app.db import Session
from app.keyboards.nav import nav, paginate

router = Router(name="profile")

@router.callback_query(F.data=="profile:open")
async def open_profile(cb: CallbackQuery):
    async with Session() as s:
        row = (await s.execute(text("select username, balance, coalesce(active_role,'user') from users where tg_id=:u"), {"u": cb.from_user.id})).first()
    username = row[0] if row else None
    balance = row[1] if row else 0
    mode = row[2] if row else "user"
    text_out = f"👤 @{username or '—'}\n💼 Режим: {mode}\n💳 Баланс: {balance} ₽"
    extra = [
        [InlineKeyboardButton(text="🧾 Мои покупки", callback_data="profile:orders:0")],
        [InlineKeyboardButton(text="➕ Пополнить баланс", callback_data="profile:topup")],
        [InlineKeyboardButton(text="🔁 Сменить режим", callback_data="profile:mode")],
    ]
    await cb.message.edit_text(text_out, reply_markup=nav(back="menu:main", extra=extra))
    await cb.answer()

@router.callback_query(F.data.regexp(r"^profile:orders:(\d+)$"))
async def my_orders(cb: CallbackQuery):
    page = int(cb.data.split(":")[2]); size=10; off=page*size
    async with Session() as s:
        rows = (await s.execute(text("""
          select p.id, p.kind, p.status, p.price, w.name, c.name
          from purchases p
          join variants v on v.id = p.variant_id
          join works w on w.id = v.work_id
          join courses c on c.id = w.course_id
          where p.buyer_id = :u
          order by p.created_at desc
          limit :lim offset :off
        """), {"u": cb.from_user.id, "lim": size, "off": off})).mappings().all()
        total = (await s.execute(text("select count(*) from purchases where buyer_id=:u"), {"u": cb.from_user.id})).scalar_one()
    if not rows:
        await cb.message.edit_text("Покупок пока нет.", reply_markup=nav(back="profile:open")); return await cb.answer()
    lines = [f"#{r['id']} • {r['name']} • {r['kind']} • {r['status']} • {r['price'] or '—'}" for r in rows]
    pager = paginate("profile:orders", page, page>0, (off+size)<total)
    await cb.message.edit_text("Мои покупки:\n\n" + "\n".join(lines), reply_markup=nav(back="profile:open", extra=pager))
    await cb.answer()

# fallback на старую кнопку
@router.callback_query(F.data=="user:orders")
async def legacy_orders(cb: CallbackQuery):
    await cb.answer()
    await cb.message.edit_text("Перенесено в профиль → Мои покупки.", reply_markup=nav(back="profile:open"))
