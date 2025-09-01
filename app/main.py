import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis
from loguru import logger

from app.config import settings
from app.db import healthcheck, Session
from app.middlewares.roles import RoleMiddleware
from app.routers.debug import debug_router
from app.routers import (
    common_router,
    redactor_router,
    admin_router,
    user_router,
    tgpay_router,
)

logger.remove()
logger.add(lambda msg: print(msg, end=""), level="DEBUG")

async def on_startup(bot: Bot):
    await healthcheck()
    logger.info("Bot started")

def build_dp() -> Dispatcher:
    storage = RedisStorage(Redis.from_url(settings.REDIS_URL))
    dp = Dispatcher(storage=storage)

    dp.update.middleware(RoleMiddleware(Session))
    
    dp.update.register(log_raw_updates, Update)

    dp.include_router(user_router)
    dp.include_router(tgpay_router)
    dp.include_router(redactor_router)
    dp.include_router(admin_router)
    dp.include_router(common_router)
    dp.include_router(debug_router)
    return dp

async def main():
    bot = Bot(settings.BOT_TOKEN)
    dp = build_dp()
    await on_startup(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
