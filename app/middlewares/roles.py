from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from typing import Callable, Awaitable, Dict, Any

class RoleMiddleware(BaseMiddleware):
    def __init__(self, roles_repo):
        self.roles_repo = roles_repo

    async def __call__(self, handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
                       event: TelegramObject, data: Dict[str, Any]):
        user = data.get("event_from_user")
        if user:
            data["roles"] = await self.roles_repo.get_user_roles(user.id)  # set[str]
        return await handler(event, data)

def requires(*need: str):
    def deco(func):
        async def wrapper(event, data):
            roles: set[str] = set(data.get("roles", []))
            if not set(need).issubset(roles):
                await data["bot"].send_message(data["event_from_user"].id, "Недостаточно прав.")
                return
            return await func(event, data)
        return wrapper
    return deco
