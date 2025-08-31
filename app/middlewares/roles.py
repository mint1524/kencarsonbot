from typing import Callable, Awaitable, Dict, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from app.repositories.roles import RolesRepo
from functools import wraps

class RoleMiddleware(BaseMiddleware):
    def __init__(self, sessionmaker):
        self.Session = sessionmaker

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ):
        roles = {"user"}  # дефолт
        user = data.get("event_from_user")
        if user:
            async with self.Session() as s:
                db_roles = await RolesRepo(s).get_user_roles(user.id)
            if db_roles:
                roles = set(db_roles)
        data["roles"] = roles
        return await handler(event, data)

def requires(*need: str):
    need = set(need)

    def deco(func):
        @wraps(func)
        async def wrapper(event: TelegramObject, **data):
            roles = set(data.get("roles", []))
            if not need.issubset(roles):
                bot = data.get("bot")
                user = data.get("event_from_user") or getattr(event, "from_user", None)
                if bot and user:
                    await bot.send_message(user.id, "Недостаточно прав.")
                return
            return await func(event, **data)
        return wrapper
    return deco
