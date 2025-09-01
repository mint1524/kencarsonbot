import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis
from loguru import logger

from app.config import settings
from app.db import healthcheck, Session
from app.middlewares.roles import RoleMiddleware
from app.routers import common, redactor, admin
from app.routers.user import user_router, tgpay_router

from app.routers.profile import router as profile_router
from app.routers.user_key import router as user_key_router
from app.routers.redactor_board import router as red_board_router
from app.routers.admin_commands import router as admin_cmd_router
from app.routers.admin_users import router as admin_users_router


async def on_startup(bot: Bot):
    await healthcheck()
    logger.info("Bot started")
    from app.workers import deadlines
    try:
        import asyncio
        asyncio.create_task(deadlines.run(bot))
    except Exception as e:
        logger.error(f"deadline worker error: {e}")

def build_dp() -> Dispatcher:
    storage = RedisStorage(Redis.from_url(settings.REDIS_URL))
    dp = Dispatcher(storage=storage)

    dp.update.middleware(RoleMiddleware(Session))

    dp.include_router(user_router)
    dp.include_router(tgpay_router)
    dp.include_router(profile_router)
    dp.include_router(user_key_router)
    dp.include_router(red_board_router)
    dp.include_router(admin_cmd_router)
    dp.include_router(admin_users_router)
    dp.include_router(redactor.router)
    dp.include_router(admin.router)
    dp.include_router(common.router)
    return dp

async def main():
    bot = Bot(settings.BOT_TOKEN)
    dp = build_dp()
    await on_startup(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
