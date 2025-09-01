from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from sqlalchemy import text
from app.db import Session
from app.keyboards.nav import nav, paginate
router = Router(name="admin_users")

@router.callback_query(F.data.regexp(r"^adm:users:(\d+)(?::(user|redactor|admin))?$"))
async def users_list(cb: CallbackQuery):
    parts = cb.data.split(":")
    page = int(parts[2])
    role = parts[3] if len(parts) > 3 else None
    size=10; off=page*size
    async with Session() as s:
        if role:
            rows = (await s.execute(text("""
              select u.tg_id, u.username, r.name as role, u.balance
              from users u
              join user_roles ur on ur.user_id=u.tg_id
              join roles r on r.id=ur.role_id
              where r.name=:role
              order by u.tg_id
              limit :l offset :o
            """), {"l": size, "o": off, "role": role})).mappings().all()
            total = (await s.execute(text("""
              select count(*) from users u
              join user_roles ur on ur.user_id=u.tg_id
              join roles r on r.id=ur.role_id
              where r.name=:role
            """), {"role": role})).scalar_one()
        else:
            rows = (await s.execute(text("""
              select u.tg_id, u.username, coalesce(string_agg(r.name, ','), 'user') as role, u.balance
              from users u
              left join user_roles ur on ur.user_id=u.tg_id
              left join roles r on r.id=ur.role_id
              group by u.tg_id, u.username, u.balance
              order by u.tg_id
              limit :l offset :o
            """), {"l": size, "o": off})).mappings().all()
            total = (await s.execute(text("select count(*) from users"))).scalar_one()
    if not rows:
        return await cb.message.edit_text("Нет пользователей.", reply_markup=nav(back="menu:main"))
    lines = [f"{r['tg_id']} • @{r['username'] or '—'} • {r['role']} • {r['balance']} ₽" for r in rows]
    filters = [
        [InlineKeyboardButton(text="Все", callback_data="adm:users:0"),
         InlineKeyboardButton(text="Только user", callback_data="adm:users:0:user"),
         InlineKeyboardButton(text="Только redactor", callback_data="adm:users:0:redactor"),
         InlineKeyboardButton(text="Только admin", callback_data="adm:users:0:admin")]
    ]
    pager = paginate("adm:users", page, page>0, (off+size)<total)
    await cb.message.edit_text("Пользователи:\n\n" + "\n".join(lines), reply_markup=nav(back="menu:main", extra=filters+pager))
    await cb.answer()
