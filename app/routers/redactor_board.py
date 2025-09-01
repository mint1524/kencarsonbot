from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import text
from app.db import Session
from app.keyboards.nav import nav, paginate

router = Router(name="red_board")

@router.callback_query(F.data.regexp(r"^red:board:(\d+)$"))
async def board_list(cb: CallbackQuery):
    page=int(cb.data.split(":")[2]); size=10; off=page*size
    async with Session() as s:
        rows = (await s.execute(text("""
          select p.id, p.price, p.deadline_at, coalesce(p.client_comment,''),
                 w.name as work_name, c.name as course
          from purchases p
          join variants v on v.id=p.variant_id
          join works w on w.id=v.work_id
          join courses c on c.id=w.course_id
          where p.kind='key' and p.status in ('paid','in_progress') and p.assigned_to is null
          order by coalesce(p.deadline_at, 'infinity'), p.created_at
          limit :l offset :o
        """), {"l": size, "o": off})).mappings().all()
        total = (await s.execute(text("""
          select count(*) from purchases
          where kind='key' and status in ('paid','in_progress') and assigned_to is null
        """))).scalar_one()
    if not rows:
        return await cb.message.edit_text("Свободных заказов нет.", reply_markup=nav(back="menu:main"))
    buttons = [[InlineKeyboardButton(
        text=f"#{r['id']} • {r['course']} — {r['work_name']} • до {r['deadline_at'] or '—'} • {r['price'] or '—'}",
        callback_data=f"red:take:{r['id']}")] for r in rows]
    pager = paginate("red:board", page, page>0, (off+size)<total)
    await cb.message.edit_text("Доступные заказы под ключ:", reply_markup=nav(back="menu:main", extra=buttons+pager))
    await cb.answer()

@router.callback_query(F.data.regexp(r"^red:take:(.+)$"))
async def take_job(cb: CallbackQuery):
    pid = cb.data.split(":")[2]
    async with Session() as s:
        await s.execute(text("""
          update purchases set assigned_to=:u, status='in_progress', updated_at=now()
          where id=:p::uuid and assigned_to is null
        """), {"u": cb.from_user.id, "p": pid})
        await s.commit()
    await cb.message.edit_text(f"Заказ {pid} взят в работу. Удачи!", reply_markup=nav(menu=True))
    await cb.answer()
