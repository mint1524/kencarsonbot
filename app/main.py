hfhfhhfhfhfimport asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery, Update
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

# logger.remove()
# logger.add(lambda msg: print(msg, end=""), level="DEBUG")

async def on_startup(bot: Bot):
    await healthcheck()
    logger.info("Bot started")
    
# async def log_raw_updates(update: Update, bot: Bot):
#     print("=== RAW UPDATE ===")
#     print(update.model_dump_json(indent=2)[:2000])
#     print("=================")

def build_dp() -> Dispatcher:
    storage = RedisStorage(Redis.from_url(settings.REDIS_URL))
    dp = Dispatcher(storage=storage)
    
    # вешаем middleware ТОЛЬКО на сообщения/колбэки
    # dp.message.middleware(RoleMiddleware(Session))
    # dp.callback_query.middleware(RoleMiddleware(Session))

    # лог вообще всех апдейтов до роутеров (чтобы понять, приходят ли)
    # async def _raw_log(update: Update, **kwargs):
    #     print("=== RAW UPDATE ===")
    #     try:
    #         print(update.model_dump_json(indent=2)[:2000])
    #     except Exception as e:
    #         print(f"(dump error: {e}) | {update}")
    #     print("==================")
    # dp.update.register(_raw_log, Update)

    # «ловушки» на случай, если твои роутеры не цепляют события
    # async def _catch_msg(msg: Message, **kwargs):
    #     print(f"[CATCH MSG] {msg.from_user.id}: {msg.text}")
    # async def _catch_cb(cb: CallbackQuery, **kwargs):
    #     print(f"[CATCH CB]  {cb.from_user.id}: {cb.data}"); await cb.answer()

    # dp.message.register(_catch_msg)
    # dp.callback_query.register(_catch_cb)

    dp.message.middleware(RoleMiddleware(Session))
    dp.callback_query.middleware(RoleMiddleware(Session))

    # dp.update.register(log_raw_updates, Update)

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
