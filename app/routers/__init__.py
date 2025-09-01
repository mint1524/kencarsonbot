from .common import router as common_router
from .user import user_router, tgpay_router
from .redactor import router as redactor_router
from .admin import router as admin_router

__all__ = [
    "common_router",
    "user_router",
    "tgpay_router",
    "redactor_router",
    "admin_router",
]
