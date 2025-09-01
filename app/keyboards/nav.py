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


from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def nav(back: str | None = None, menu: bool = True, cancel: str | None = None, extra: list[list[InlineKeyboardButton]] | None = None) -> InlineKeyboardMarkup:
    rows = list(extra) if extra else []
    ctrl = []
    if back:
        ctrl.append(InlineKeyboardButton(text="🔙 Назад", callback_data=back))
    if menu:
        ctrl.append(InlineKeyboardButton(text="🏠 Меню", callback_data="menu:main"))
    if cancel:
        ctrl.append(InlineKeyboardButton(text="✖️ Отмена", callback_data=cancel))
    if ctrl:
        rows.append(ctrl)
    return InlineKeyboardMarkup(inline_keyboard=rows)

def paginate(prefix: str, page: int, has_prev: bool, has_next: bool):
    row = []
    if has_prev:
        row.append(InlineKeyboardButton(text="◀", callback_data=f"{prefix}:{page-1}"))
    if has_next:
        row.append(InlineKeyboardButton(text="▶", callback_data=f"{prefix}:{page+1}"))
    return [row] if row else [[InlineKeyboardButton(text="↻ Обновить", callback_data=f"{prefix}:{page}")]]
