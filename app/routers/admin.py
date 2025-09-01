from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from sqlalchemy import text
from app.middlewares.roles import Requires, MissingRole
from app.db import Session
from app.repositories.roles import RolesRepo, VALID_ROLES
from app.repositories.works import WorksRepo
from app.keyboards.admin import moderation_list_kb, work_card_kb, save_prices_kb
from app.keyboards.nav import back_to_menu_kb

# --- корневой роутер
router = Router(name="admin_root")

@router.callback_query(MissingRole("admin"), F.data.regexp(r"^adm:"))
async def admin_gate(cb: CallbackQuery):
    await cb.answer("Недостаточно прав.", show_alert=True)
    return

# --- подроутер «админ-команды»
admin_cmd = Router(name="admin_cmd")

@admin_cmd.message(Requires("admin"), F.text.regexp(r"^/promote (\d+) (.+)$"))
async def promote_user(msg: Message):
    tg_id, roles_str = msg.text.split(maxsplit=2)[1:]
    tg_id = int(tg_id)
    roles = [r.strip() for r in roles_str.split(",")]
    async with Session() as s:
        repo = RolesRepo(s)
        added = []
        for role in roles:
            if role not in VALID_ROLES:
                await msg.answer(f"⚠️ Роль '{role}' недопустима. Доступные: {', '.join(VALID_ROLES)}")
                continue
            await repo.add_role(tg_id, role)
            added.append(role)
    if added:
        await msg.answer(f"✅ Пользователь {tg_id} получил роли: {', '.join(added)}")

@admin_cmd.message(Requires("admin"), F.text.regexp(r"^/demote (\d+) (.+)$"))
async def demote_user(msg: Message):
    tg_id, roles_str = msg.text.split(maxsplit=2)[1:]
    tg_id = int(tg_id)
    roles = [r.strip() for r in roles_str.split(",")]
    async with Session() as s:
        repo = RolesRepo(s)
        removed = []
        for role in roles:
            if role not in VALID_ROLES:
                await msg.answer(f"⚠️ Роль '{role}' недопустима. Доступные: {', '.join(VALID_ROLES)}")
                continue
            await repo.remove_role(tg_id, role)
            removed.append(role)
    if removed:
        await msg.answer(f"❌ У пользователя {tg_id} сняты роли: {', '.join(removed)}")

@admin_cmd.callback_query(Requires("admin"), F.data == "adm:users")
async def list_users(cb: CallbackQuery):
    async with Session() as s:
        rows = (await s.execute(text("""
          select tg_id, coalesce(username, '') as username, balance
            from users order by created_at desc limit 20
        """))).mappings().all()
    if not rows:
        await cb.message.edit_text("Пользователей пока нет.", reply_markup=back_to_menu_kb())
    else:
        text_out = "Пользователи:\n\n" + "\n".join(
            f"{r['tg_id']} • @{r['username']} • баланс {r['balance']}" for r in rows
        )
        await cb.message.edit_text(text_out, reply_markup=back_to_menu_kb())
    await cb.answer()

# --- подроутер «модерация»
admin_mod = Router(name="admin_mod")

@admin_mod.callback_query(Requires("admin"), F.data == "adm:moderation")
async def mod_entry(cb: CallbackQuery):
    await cb.answer()
    await list_page(cb, 0)

@admin_mod.callback_query(Requires("admin"), F.data.regexp(r"^adm:mod:list:(\d+)$"))
async def mod_list(cb: CallbackQuery):
    page = int(cb.data.rsplit(":",1)[1])
    await list_page(cb, page)

async def list_page(cb: CallbackQuery, page: int):
    async with Session() as s:
        rows, has_next = await WorksRepo(s).list_for_moderation(page)
    if not rows:
        await cb.message.edit_text("Пока нечего модерировать.")
        return
    lines = []
    for r in rows:
        lines.append(f"#{r['id']} • {r['course_name']} — {r['name']} • {r['author_name']} • "
                     f"Готовая: {r['price_regular'] or '—'} | Под ключ: {r['price_key'] or '—'}\n"
                     f"/card_{r['id']}")
    text_out = "Модерация работ:\n\n" + "\n".join(lines)
    await cb.message.edit_text(text_out, reply_markup=moderation_list_kb(page, page>0, has_next))

@admin_mod.callback_query(Requires("admin"), F.text.regexp(r"^/card_(\d+)$"))
async def show_card(msg: Message):
    work_id = int(msg.text.split("_")[1])
    async with Session() as s:
        card = await WorksRepo(s).get_card(work_id)
    txt = (f"#{card['id']} • {card['course_name']}\n"
           f"Название: {card['name']}\n"
           f"Статус: {card['status']}\n"
           f"Готовая: {card['price_regular'] or '—'} | Под ключ: {card['price_key'] or '—'}\n\n"
           f"{card['description'] or ''}")
    await msg.answer(txt, reply_markup=work_card_kb(work_id))

@admin_mod.callback_query(Requires("admin"), F.data.regexp(r"^adm:mod:card:(\d+)$"))
async def card_from_btn(cb: CallbackQuery):
    wid = int(cb.data.rsplit(":",1)[1])
    async with Session() as s:
        card = await WorksRepo(s).get_card(wid)
    txt = (f"#{card['id']} • {card['course_name']}\n"
           f"Название: {card['name']}\n"
           f"Статус: {card['status']}\n"
           f"Готовая: {card['price_regular'] or '—'} | Под ключ: {card['price_key'] or '—'}")
    await cb.message.edit_text(txt, reply_markup=work_card_kb(wid)); await cb.answer()

class EditPriceFSM(StatesGroup):
    input = State()

@admin_mod.callback_query(Requires("admin"), F.data.regexp(r"^adm:mod:edit_prices:(\d+)$"))
async def edit_prices_start(cb: CallbackQuery, state: FSMContext):
    wid = int(cb.data.rsplit(":",1)[1])
    await state.set_state(EditPriceFSM.input)
    await state.update_data(work_id=wid)
    await cb.message.edit_text("Введи цены через пробел: <готовая> <под_ключ>\nПример: `1990 4990`\n"
                               "Если варианта нет — поставь `-`.", parse_mode="Markdown",
                               reply_markup=save_prices_kb(wid))
    await cb.answer()

@admin_mod.message(Requires("admin"), EditPriceFSM.input)
async def edit_prices_save(msg: Message, state: FSMContext):
    parts = (msg.text.split() + ["",""])[:2]
    def parse(x): return None if x.strip()=="-" else float(x)
    pr, pk = parse(parts[0]), parse(parts[1])
    data = await state.get_data()
    async with Session() as s:
        await WorksRepo(s).update_prices(data["work_id"], pr, pk)
    await state.clear()
    await msg.answer("Цены обновлены. /card_{}".format(data["work_id"]))

@admin_mod.callback_query(Requires("admin"), F.data.regexp(r"^adm:mod:save_prices:(\d+)$"))
async def save_prices_click(cb: CallbackQuery):
    await cb.answer("Введи цены сообщением в чат — см. инструкцию выше.", show_alert=True)

@admin_mod.callback_query(Requires("admin"), F.data.regexp(r"^adm:mod:approve:(\d+)$"))
async def approve_work(cb: CallbackQuery):
    wid = int(cb.data.rsplit(":",1)[1])
    async with Session() as s:
        await WorksRepo(s).approve(wid)
    await cb.message.edit_text(f"Работа #{wid} одобрена и переведена в статус READY.")
    await cb.answer()

@admin_mod.callback_query(Requires("admin"), F.data.regexp(r"^adm:mod:reject:(\d+)$"))
async def reject_work(cb: CallbackQuery):
    wid = int(cb.data.rsplit(":",1)[1])
    async with Session() as s:
        await WorksRepo(s).reject(wid)
    await cb.message.edit_text(f"Работа #{wid} возвращена в NOT_IN_PROGRESS.")
    await cb.answer()

# --- подключаем подроутеры к корневому
router.include_router(admin_cmd)
router.include_router(admin_mod)
