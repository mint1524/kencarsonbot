from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
Session = async_sessionmaker(engine, expire_on_commit=False)

async def healthcheck():
    async with engine.connect() as conn:
        await conn.execute(text("select 1"))
