from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

class RolesRepo:
    def __init__(self, s: AsyncSession):
        self.s = s

    async def get_user_roles(self, user_id: int) -> set[str]:
        q = text("""
            select r.name from roles r
            join user_roles ur on ur.role_id = r.id
            where ur.user_id = :u
        """)
        rows = (await self.s.execute(q, {"u": user_id})).scalars().all()
        return set(rows) if rows else {"user"}   # базовая роль по умолчанию

    async def grant_role(self, user_id: int, role_name: str):
        q = text("select id from roles where name = :n")
        role_id = (await self.s.execute(q, {"n": role_name})).scalar_one()
        q2 = text("""
            insert into user_roles(user_id, role_id)
            values (:u, :r) on conflict do nothing
        """)
        await self.s.execute(q2, {"u": user_id, "r": role_id})
        await self.s.commit()
