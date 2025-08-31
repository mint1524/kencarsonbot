from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.config import settings
from app.services.payments import CryptoPay
from aiogram import Bot
from app.services.tg_payments import label_price

class ShopService:
    def __init__(self, s: AsyncSession):
        self.s = s
        
    async def create_purchase_tg_invoice(self, bot: Bot, chat_id: int, buyer_id: int, variant_id: int, kind: str):
        # 1) берём цену
        q = text("select work_id, price_key, price_regular from variants where id=:v")
        work_id, price_key, price_reg = (await self.s.execute(q, {"v": variant_id})).one()
        price = price_reg if kind == "ready" else price_key
        if price is None:
            raise ValueError("Этот вариант недоступен для выбранного вида")

        # 2) создаём покупку (pending)
        pid = (await self.s.execute(text("""
          insert into purchases (buyer_id, variant_id, kind, status)
          values (:b,:v,:k,'pending') returning id::text
        """), {"b": buyer_id, "v": variant_id, "k": kind})).scalar_one()

        # 3) отправляем счёт
        title = f"Покупка варианта #{variant_id} ({'готовая' if kind=='ready' else 'под ключ'})"
        description = "Оплата через Telegram Payments (СБП/карта)."
        prices = label_price(float(price))
        payload = pid  # это вернётся в successful_payment

        msg = await bot.send_invoice(
            chat_id=chat_id,
            title=title,
            description=description,
            payload=payload,
            provider_token=settings.TG_PAY_PROVIDER_TOKEN,
            currency="RUB",
            prices=prices,
            start_parameter=f"buy_{variant_id}_{kind}"
        )

        # 4) логируем payment (pending, без id до pre_checkout/успеха)
        await self.s.execute(text("""
            insert into payments (purchase_id, provider, currency, amount, status, raw)
            values (:pid, 'telegram', 'RUB', :amt, 'pending', '{}'::jsonb)
        """), {"pid": pid, "amt": float(price)})
        await self.s.commit()
        return pid, msg.invoice_link  if hasattr(msg, "invoice_link") else None

    async def create_purchase_with_invoice(self, buyer_id: int, variant_id: int, kind: str, currency: str):
        # 1) вытащим цену по требуемому виду
        q = text("select work_id, price_key, price_regular from variants where id=:v")
        work_id, price_key, price_reg = (await self.s.execute(q, {"v": variant_id})).one()
        price = price_reg if kind == "ready" else price_key
        if price is None:
            raise ValueError("Этот вариант недоступен для выбранного вида")

        # 2) создаём покупку (pending)
        q2 = text("""
          insert into purchases (buyer_id, variant_id, kind, status)
          values (:b, :v, :k, 'pending') returning id::text
        """)
        purchase_id = (await self.s.execute(q2, {"b": buyer_id, "v": variant_id, "k": kind})).scalar_one()

        # 3) создаём инвойс в Crypto Pay
        cp = CryptoPay(settings.CRYPTO_PAY_TOKEN)
        inv = await cp.create_invoice(
            amount=float(price),
            currency=currency,
            description=f"Покупка варианта {variant_id} ({kind})",
            payload=purchase_id,
            lifetime=int(settings.CRYPTO_PAY_LIFETIME)
        )

        # 4) сохраним payment-лог
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
        # 1) найдём payment и покупку
        q = text("""
          select p.purchase_id, p.status, p.amount, p.currency, p.external_id
          from payments p where p.external_id = :ext and provider='cryptobot'
        """)
        row = (await self.s.execute(q, {"ext": str(invoice_id)})).first()
        if not row:
            return False, "invoice_not_found"
        purchase_id, pay_status, amount, currency, ext = row

        # 2) проверим у провайдера
        cp = CryptoPay(settings.CRYPTO_PAY_TOKEN)
        inv = await cp.get_invoice(int(ext))
        if not inv:
            return False, "not_found_remote"

        if inv["status"] != "paid":
            # обновим статус, если поменялся
            if pay_status != inv["status"]:
                await self.s.execute(text("update payments set status=:s, raw=:raw where external_id=:e"),
                                     {"s": inv["status"], "raw": inv, "e": ext})
                await self.s.commit()
            return False, inv["status"]

        # 3) закрываем покупку (если ещё не закрыта)
        q2 = text("select buyer_id, variant_id, kind, status from purchases where id=:id for update")
        buyer_id, variant_id, kind, pstatus = (await self.s.execute(q2, {"id": purchase_id})).one()
        if pstatus == "paid":
            return True, "already_paid"

        # получим автора
        q3 = text("""
          select w.author from variants v join works w on w.id = v.work_id
          where v.id = :v
        """)
        author_id = (await self.s.execute(q3, {"v": variant_id})).scalar_one()

        # 4) фиксируем цену и статус покупки
        await self.s.execute(text("""
          update purchases set price=:p, status='paid', updated_at=now()
          where id=:id
        """), {"p": amount, "id": purchase_id})

        # 5) начисляем 70/30 (если автор не сам покупатель — иначе 0/100)
        author_share = 0.0 if buyer_id == author_id else round(float(amount) * 0.70, 2)
        platform_share = round(float(amount) - author_share, 2)

        await self.s.execute(text("update users set balance = balance + :x where tg_id=:u"),
                             {"x": author_share, "u": author_id})
        await self.s.execute(text("update users set balance = balance + :x where tg_id=:u"),
                             {"x": platform_share, "u": settings.PLATFORM_USER_ID})

        # 6) обновим payment
        await self.s.execute(text("""
          update payments set status='paid', updated_at=now(), raw=:raw where external_id=:e
        """), {"raw": inv, "e": ext})

        # 7) для 'key' переведём работу в in_progress
        if kind == "key":
            await self.s.execute(text("""
              update works set status='in_progress', updated_at=now()
              where id = (select work_id from variants where id=:v)
            """), {"v": variant_id})

        await self.s.commit()
        return True, "paid"
