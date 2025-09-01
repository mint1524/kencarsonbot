from typing import Callable, Awaitable, Dict, Any, Optional, Set
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.filters import BaseFilter

from app.repositories.roles import RolesRepo

class RoleMiddleware(BaseMiddleware):
    def __init__(self, sessionmaker):
        self.Session = sessionmaker

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ):
        user = data.get("event_from_user")
        if user:
            async with self.Session() as s:
                roles = await RolesRepo(s).get_user_roles(user.id)
            data["roles"] = roles or {"user"}
        return await handler(event, data)


# def requires(*need: str):
#     """Декоратор для aiogram v3: НЕ ломает DI, принимает **data и пробрасывает дальше."""
#     need_set = set(need)

#     def deco(func):
#         @functools.wraps(func)
#         async def wrapper(event: TelegramObject, data: Dict[str, Any]):
#             roles: set[str] = set(data.get("roles", []))
#             if not need_set.issubset(roles):
#                 bot = data["bot"]
#                 user = data.get("event_from_user")
#                 if user:
#                     await bot.send_message(user.id, "Недостаточно прав.")
#                 return
#             # важно: пробрасываем дальше ТЕМ ЖЕ контрактом (event, data)
#             return await func(event, data)
#         return wrapper
#     return deco

class Requires(BaseFilter):
    """Тихий фильтр ролей: возвращает True/False, без сообщений пользователю.
       Если roles ещё не проставлены мидлварью, подгружает их как запасной вариант."""
    def __init__(self, *need: str):
        self.need: Set[str] = set(need)

    async def __call__(
        self,
        event: TelegramObject,
        roles: Optional[Set[str]] = None,
        event_from_user=None,
        bot=None,
        **_
    ) -> bool:
        if roles is None and event_from_user is not None:
            # запасной план: получить роли напрямую (на случай если мидлварь не сработала)
            from app.db import Session  # локальный импорт, чтобы не плодить циклы
            async with Session() as s:
                roles = await RolesRepo(s).get_user_roles(event_from_user.id)
        roles = roles or set()
        return self.need.issubset(roles)
