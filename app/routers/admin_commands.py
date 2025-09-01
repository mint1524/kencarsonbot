from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy import text
from app.db import Session
from app.middlewares.roles import requires

router = Router(name="admin_cmd")

@router.message(F.text.regexp(r"^/commission\s+(\d{1,2}|100)$"))
@requires("admin")
async def set_commission(msg: Message):
    pct = int(msg.text.split()[1])
    async with Session() as s:
        await s.execute(text("insert into settings(key,value) values('platform_commission_percent', :v) on conflict(key) do update set value=:v"), {"v": str(pct)})
        await s.commit()
    await msg.answer(f"Комиссия платформы установлена: {pct}%")

@router.message(F.text.regexp(r"^/money\s+(.+)\s+([+=-]?\d+)$"))
@requires("admin")
async def money(msg: Message):
    ids, val = msg.text.split()[1], msg.text.split()[2]
    val_int = int(val)
    targets = []
    if ids.lower() == "all":
        async with Session() as s:
            targets = (await s.execute(text("select tg_id from users"))).scalars().all()
    elif ids.startswith("(") and ids.endswith(")"):
        targets = [int(x.strip()) for x in ids[1:-1].split(",")]
    else:
        targets = [int(ids)]
    async with Session() as s:
        for uid in targets:
            if val.startswith(("+","-")):
                await s.execute(text("update users set balance = balance + :d where tg_id=:u"), {"d": val_int, "u": uid})
            else:
                await s.execute(text("update users set balance = :d where tg_id=:u"), {"d": val_int, "u": uid})
        await s.commit()
    await msg.reply(f"Ок. Обработано {len(targets)} пользователя(ей).")
