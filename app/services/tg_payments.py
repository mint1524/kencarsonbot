from aiogram.types import LabeledPrice
from decimal import Decimal, ROUND_HALF_UP

def rub_to_kopecks(val: float | Decimal) -> int:
    d = Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(d * 100)

def label_price(amount_rub: float, label: str = "Оплата") -> list[LabeledPrice]:
    return [LabeledPrice(label=label, amount=rub_to_kopecks(amount_rub))]
