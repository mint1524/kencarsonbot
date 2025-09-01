from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 В меню", callback_data="menu:main")]
    ])

def with_back(kb: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    # аккуратно добавляем ряд "Назад" в конец любой клавы
    rows = list(kb.inline_keyboard)
    rows.append([InlineKeyboardButton(text="🔙 В меню", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="fsm:cancel")]
        ]
    )
