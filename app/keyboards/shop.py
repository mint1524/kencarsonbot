from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def shop_list_kb(page: int, has_prev: bool, has_next: bool):
    row = []
    if has_prev: row.append(InlineKeyboardButton(text="◀", callback_data=f"user:shop:list:{page-1}"))
    if has_next: row.append(InlineKeyboardButton(text="▶", callback_data=f"user:shop:list:{page+1}"))
    return InlineKeyboardMarkup(inline_keyboard=[row] if row else [[InlineKeyboardButton(text="↻", callback_data=f"user:shop:list:{page}")]])

def variant_buy_kb(variant_id: int, can_ready: bool, can_key: bool):
    rows = []
    if can_ready: rows.append([InlineKeyboardButton(text="Купить: Готовая", callback_data=f"user:buy:ready:{variant_id}")])
    if can_key: rows.append([InlineKeyboardButton(text="Купить: Под ключ", callback_data=f"user:buy:key:{variant_id}")])
    if can_ready: rows.append([InlineKeyboardButton(text="Купить: Готовая (RUB)", callback_data=f"user:buy_tg:ready:{variant_id}")])
    if can_key:   rows.append([InlineKeyboardButton(text="Купить: Под ключ (RUB)", callback_data=f"user:buy_tg:key:{variant_id}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="user:shop:list:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
