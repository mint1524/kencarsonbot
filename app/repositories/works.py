from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

class WorksRepo:
    def __init__(self, s: AsyncSession): self.s = s

    async def list_for_moderation(self, page: int, page_size: int = 10):
        off = page * page_size
        q = text("""
          select w.id, w.name, w.status, u.username as author_name, w.author,
                 v.price_regular, v.price_key, c.name as course_name
          from works w
          join variants v on v.work_id = w.id
          join users u on u.tg_id = w.author
          join courses c on c.id = w.course_id
          where w.status in ('not_in_progress','ready') -- что именно модерировать
          order by w.created_at desc
          limit :lim offset :off
        """)
        rows = (await self.s.execute(q, {"lim": page_size, "off": off})).mappings().all()
        # проверим есть ли следующая страница
        q2 = text("select count(*) from works")
        total = (await self.s.execute(q2)).scalar_one()
        has_next = (off + page_size) < total
        return rows, has_next

    async def get_card(self, work_id: int):
        q = text("""
          select w.id, w.name, w.description, w.status, w.author, c.name as course_name,
                 v.id as variant_id, v.price_regular, v.price_key
          from works w
          join variants v on v.work_id = w.id
          join courses c on c.id = w.course_id
          where w.id = :w
        """)
        return (await self.s.execute(q, {"w": work_id})).mappings().one()

    async def update_prices(self, work_id: int, pr: float | None, pk: float | None):
        q = text("""update variants set price_regular=:pr, price_key=:pk where work_id=:w""")
        await self.s.execute(q, {"pr": pr, "pk": pk, "w": work_id})
        await self.s.commit()

    async def approve(self, work_id: int):
        q = text("""update works set status='ready', updated_at=now() where id=:w""")
        await self.s.execute(q, {"w": work_id}); await self.s.commit()

    async def reject(self, work_id: int):
        q = text("""update works set status='not_in_progress', updated_at=now() where id=:w""")
        await self.s.execute(q, {"w": work_id}); await self.s.commit()
