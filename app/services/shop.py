from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from aiogram import Bot
from app.config import settings
from app.services.payments import CryptoPay
from sqlalchemy import text as _text
async def _author_percent(session):
    row = (await session.execute(_text("select value from settings where key='platform_commission_percent'"))).first()
    pct = int(row[0]) if row else 30
    return (100 - pct) / 100

class ShopService:
    def __init__(self, s: AsyncSession):
        self.s = s

    # ---------- Вспомогательные ----------
    async def _get_price(self, variant_id: int, kind: str):
        q = text("select work_id, price_key, price_regular from variants where id=:v")
        row = (await self.s.execute(q, {"v": variant_id})).first()
        if not row:
            raise ValueError("Вариант не найден")
        work_id, price_key, price_reg = row
        price = price_reg if kind == "ready" else price_key
        if price is None:
            raise ValueError("Этот вариант недоступен для выбранного вида")
        return int(work_id), float(price)

    async def get_ready_asset_for_variant(self, variant_id: int):
        r = (await self.s.execute(text("""
            select a.tg_file_id, a.file_name
              from assets a
              join variants v on v.work_id = a.work_id
             where v.id = :vid and a.kind='ready'
             order by a.created_at desc
             limit 1
        """), {"vid": variant_id})).mappings().first()
        return r  # dict | None

    async def get_purchase_brief(self, purchase_id: str):
        return (await self.s.execute(text("""
            select p.id::text as id, p.buyer_id, p.variant_id, p.kind, p.status
              from purchases p
             where p.id=:id::uuid
        """), {"id": purchase_id})).mappings().one()

    # ---------- Telegram Payments (RUB) ----------
    async def create_purchase_tg_invoice(self, bot: Bot, chat_id: int, buyer_id: int, variant_id: int, kind: str):
        work_id, price = await self._get_price(variant_id, kind)

        # покупка pending
        purchase_id = (await self.s.execute(text("""
            insert into purchases (buyer_id, variant_id, kind, status)
            values (:b,:v,:k,'pending') returning id::text
        """), {"b": buyer_id, "v": variant_id, "k": kind})).scalar_one()

        title = f"Покупка варианта #{variant_id} ({'готовая' if kind=='ready' else 'под ключ'})"
        description = "Оплата через Telegram Payments."
        prices = label_price(price)

        msg = await bot.send_invoice(
            chat_id=chat_id,
            title=title,
            description=description,
            payload=purchase_id,   # вернётся как successful_payment.invoice_payload
            provider_token=settings.TG_PAY_PROVIDER_TOKEN,
            currency="RUB",
            prices=prices,
            start_parameter=f"buy_{variant_id}_{kind}"
        )

        # лог платежа (pending)
        await self.s.execute(text("""
            insert into payments (purchase_id, provider, currency, amount, status)
            values (:pid, 'telegram', 'RUB', :amt, 'pending')
        """), {"pid": purchase_id, "amt": price})
        await self.s.commit()
        return purchase_id, getattr(msg, "invoice_link", None)

    # ---------- Crypto Pay ----------
    async def create_purchase_with_invoice(self, buyer_id: int, variant_id: int, kind: str, currency: str):
        work_id, price = await self._get_price(variant_id, kind)

        # покупка pending
        purchase_id = (await self.s.execute(text("""
            insert into purchases (buyer_id, variant_id, kind, status)
            values (:b,:v,:k,'pending') returning id::text
        """), {"b": buyer_id, "v": variant_id, "k": kind})).scalar_one()

        cp = CryptoPay(settings.CRYPTO_PAY_TOKEN)
        inv = await cp.create_invoice(
            amount=float(price),
            currency=currency,  # USDT/TON/...
            description=f"Покупка варианта {variant_id} ({kind})",
            payload=purchase_id,
            lifetime=int(settings.CRYPTO_PAY_LIFETIME)
        )

        # лог платежа cryptobot (pending)
        await self.s.execute(text("""
            insert into payments (purchase_id, provider, currency, amount, status, external_id, raw)
            values (:pid, 'cryptobot', :cur, :amt, :st, :ext, :raw)
        """), {
            "pid": purchase_id, "cur": currency, "amt": float(price),
            "st": inv["status"], "ext": str(inv["invoice_id"]), "raw": inv
        })
        await self.s.commit()
        return purchase_id, inv["pay_url"], inv["invoice_id"], float(price)

    async def check_and_settle(self, invoice_id: int):
        """
        Проверяем cryptobot-инвойс и закрываем покупку.
        Возвращает: (ok: bool, status: str, info: dict|None)
        info = {purchase_id, buyer_id, variant_id, kind}
        """
        # найдём платёж
        row = (await self.s.execute(text("""
            select p.purchase_id, p.status, p.amount, p.currency, p.external_id
              from payments p
             where p.external_id = :ext and provider='cryptobot'
        """), {"ext": str(invoice_id)})).first()
        if not row:
            return False, "invoice_not_found", None
        purchase_id, pay_status, amount, currency, ext = row

        # спросим у провайдера
        cp = CryptoPay(settings.CRYPTO_PAY_TOKEN)
        inv = await cp.get_invoice(int(ext))
        if not inv:
            return False, "not_found_remote", None

        # обновим статус платежа, если поменялся
        if pay_status != inv["status"]:
            await self.s.execute(text("update payments set status=:s, raw=:raw, updated_at=now() where external_id=:e"),
                                 {"s": inv["status"], "raw": inv, "e": ext})
            await self.s.commit()

        if inv["status"] != "paid":
            return False, inv["status"], None

        # закроем покупку (лок)
        br = (await self.s.execute(text("""
            select buyer_id, variant_id, kind, status
              from purchases where id=:id::uuid for update
        """), {"id": purchase_id})).first()
        if not br:
            return False, "purchase_not_found", None
        buyer_id, variant_id, kind, pstatus = br
        if pstatus in ("paid", "in_progress", "done"):
            # уже обработана ранее
            return True, "already_processed", {"purchase_id": purchase_id, "buyer_id": buyer_id, "variant_id": variant_id, "kind": kind}

        # автор работы
        author_id = (await self.s.execute(text("""
            select w.author from variants v join works w on w.id = v.work_id
             where v.id = :v
        """), {"v": variant_id})).scalar_one()

        # фиксируем цену и статус покупки:
        # - ready  -> status='paid'
        # - key    -> status='in_progress'
        new_status = "paid" if kind == "ready" else "in_progress"
        await self.s.execute(text("""
            update purchases set price=:p, status=:st, updated_at=now()
             where id=:id::uuid
        """), {"p": float(amount), "st": new_status, "id": purchase_id})

        # начисления 70/30
        author_share = 0.0 if buyer_id == author_id else round(float() * await _author_percent(self.s), 2)
        platform_share = round(float(amount) - author_share, 2)
        await self.s.execute(text("update users set balance = balance + :x where tg_id=:u"),
                             {"x": author_share, "u": author_id})
        await self.s.execute(text("update users set balance = balance + :x where tg_id=:u"),
                             {"x": platform_share, "u": settings.PLATFORM_USER_ID})

        # обновим payment
        await self.s.execute(text("""
            update payments set status='paid', updated_at=now(), raw=:raw
             where external_id=:e
        """), {"raw": inv, "e": ext})

        # для 'key' переведём работу в in_progress
        if kind == "key":
            await self.s.execute(text("""
                update works set status='in_progress', updated_at=now()
                 where id = (select work_id from variants where id=:v)
            """), {"v": variant_id})

        await self.s.commit()
        return True, "paid", {"purchase_id": purchase_id, "buyer_id": buyer_id, "variant_id": variant_id, "kind": kind}
