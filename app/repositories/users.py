from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

class UsersRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def upsert_user(self, tg_id: int, username: str | None):
        q = text("""
            insert into users (tg_id, username) values (:tg, :un)
            on conflict (tg_id) do update set username = excluded.username
        """)
        await self.s.execute(q, {"tg": tg_id, "un": username})
        await self.s.commit()

    async def add_balance(self, user_id: int, delta: float):
        q = text("update users set balance = balance + :d where tg_id = :u")
        await self.s.execute(q, {"d": delta, "u": user_id})
        await self.s.commit()

    async def get_balance(self, user_id: int) -> float:
        q = text("select balance from users where tg_id = :u")
        res = await self.s.execute(q, {"u": user_id})
        return float(res.scalar_one())
