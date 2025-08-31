import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis
from loguru import logger

from app.config import settings
from app.db import healthcheck, Session
from app.middlewares.roles import RoleMiddleware
from app.repositories.roles import RolesRepo
from app.routers import common, user, redactor, admin

async def on_startup(bot: Bot):
    await healthcheck()
    logger.info("Bot started")

def build_dp() -> Dispatcher:
    storage = RedisStorage(Redis.from_url(settings.REDIS_URL))
    dp = Dispatcher(storage=storage)
    # repo factory для middleware
    async def repo_factory():
        async with Session() as s:
            yield RolesRepo(s)
    dp.message.middleware(RoleMiddleware(RolesRepo(next(asyncio.run(repo_factory())))))  # упрощённо
    dp.callback_query.middleware(RoleMiddleware(RolesRepo(next(asyncio.run(repo_factory())))))
    dp.include_router(common.router)
    dp.include_router(user.router)
    dp.include_router(redactor.router)
    dp.include_router(admin.router)
    return dp

async def main():
    bot = Bot(settings.BOT_TOKEN)
    dp = build_dp()
    await on_startup(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
