from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu(roles: set[str]) -> InlineKeyboardMarkup:
    buttons = []
    # Базовые (user)
    buttons += [
        [InlineKeyboardButton(text="🛍 Купить работу", callback_data="user:shop")],
        [InlineKeyboardButton(text="📦 Мои покупки", callback_data="user:orders")],
    ]
    if "redactor" in roles:
        buttons += [
            [InlineKeyboardButton(text="🧰 Мои работы", callback_data="red:works")],
            [InlineKeyboardButton(text="⬆️ Загрузить работу", callback_data="red:upload")],
            [InlineKeyboardButton(text="💰 Кошелёк / Вывод", callback_data="red:wallet")],
        ]
    if "admin" in roles:
        buttons += [
            [InlineKeyboardButton(text="✅ Модерация", callback_data="adm:moderation")],
            [InlineKeyboardButton(text="👤 Пользователи", callback_data="adm:users")],
        ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
