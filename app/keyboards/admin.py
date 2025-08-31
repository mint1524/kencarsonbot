from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def moderation_list_kb(page: int, has_prev: bool, has_next: bool):
    row = []
    if has_prev: row.append(InlineKeyboardButton(text="◀", callback_data=f"adm:mod:list:{page-1}"))
    if has_next: row.append(InlineKeyboardButton(text="▶", callback_data=f"adm:mod:list:{page+1}"))
    if not row: row = [InlineKeyboardButton(text="↻ Обновить", callback_data=f"adm:mod:list:{page}")]
    return InlineKeyboardMarkup(inline_keyboard=[row])

def work_card_kb(work_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Править цены", callback_data=f"adm:mod:edit_prices:{work_id}")],
        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"adm:mod:approve:{work_id}")],
        [InlineKeyboardButton(text="⛔ Отклонить", callback_data=f"adm:mod:reject:{work_id}")],
        [InlineKeyboardButton(text="🔙 Назад к списку", callback_data="adm:mod:list:0")],
    ])

def save_prices_kb(work_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Сохранить", callback_data=f"adm:mod:save_prices:{work_id}")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data=f"adm:mod:card:{work_id}")],
    ])
