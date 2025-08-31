import aiohttp
from typing import Literal

class CryptoPay:
    def __init__(self, token: str, base: str = "https://pay.crypt.bot/api"):
        self.base = base
        self.headers = {"Crypto-Pay-API-Token": token}

    async def create_invoice(self, amount: float, currency: str, description: str, payload: str, lifetime: int = 900):
        async with aiohttp.ClientSession(headers=self.headers) as s:
            data = {
                "amount": str(amount),
                "currency_type": "fiat" if currency == "RUB" else "crypto",
                "asset": currency,                  # USDT/TON/...
                "description": description[:1024],
                "paid_btn_name": "callback",
                "paid_btn_url": "https://t.me/",
                "payload": payload,
                "expires_in": lifetime
            }
            async with s.post(f"{self.base}/createInvoice", json=data) as r:
                js = await r.json()
                if not js.get("ok"):
                    raise RuntimeError(f"CryptoPay error: {js}")
                return js["result"]                # {invoice_id, pay_url, status, ...}

    async def get_invoice(self, invoice_id: int):
        async with aiohttp.ClientSession(headers=self.headers) as s:
            async with s.get(f"{self.base}/getInvoices?invoice_ids={invoice_id}") as r:
                js = await r.json()
                if not js.get("ok"):
                    raise RuntimeError(f"CryptoPay get error: {js}")
                items = js["result"]["items"]
                return items[0] if items else None  # {..., "status": "paid"|"active"|...}
