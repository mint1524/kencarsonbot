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

    async def add_role(self, user_id: int, role_name: str):
        if role_name not in VALID_ROLES:
            raise ValueError(f"Недопустимая роль: {role_name}")

        rid = (await self.s.execute(
            text("select id from roles where name=:r"),
            {"r": role_name}
        )).scalar_one_or_none()

        if rid is None:
            rid = (await self.s.execute(
                text("insert into roles(name) values (:r) returning id"),
                {"r": role_name}
            )).scalar_one()

        await self.s.execute(
            text("""
                insert into user_roles(user_id, role_id)
                values (:u, :r) on conflict do nothing
            """),
            {"u": user_id, "r": rid}
        )
        await self.s.commit()

    async def remove_role(self, user_id: int, role_name: str):
        if role_name not in VALID_ROLES:
            raise ValueError(f"Недопустимая роль: {role_name}")

        q = text("""
            delete from user_roles
            where user_id=:u
              and role_id=(select id from roles where name=:r)
        """)
        await self.s.execute(q, {"u": user_id, "r": role_name})
        await self.s.commit()