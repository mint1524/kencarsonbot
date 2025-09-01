from . import common
from .user import user_router, tgpay_router
from . import redactor
from . import admin

# чтобы main.py мог импортировать:
router = common.router  # не используется, но оставим для совместимости
