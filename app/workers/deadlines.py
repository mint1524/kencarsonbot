import asyncio
from sqlalchemy import text
from app.db import Session

async def run(bot):
    while True:
        async with Session() as s:
            rows = (await s.execute(text("""
              select id, assigned_to
              from purchases
              where kind='key' and status='in_progress' and assigned_to is not null
                and deadline_at is not null
                and (deadline_at - now()) between interval '0' and interval '2 hours'
            """))).mappings().all()
        for r in rows:
            try:
                await bot.send_message(r["assigned_to"], f"⏰ Дедлайн по заказу {r['id']} через 2 часа!")
            except Exception:
                pass
        await asyncio.sleep(600)
