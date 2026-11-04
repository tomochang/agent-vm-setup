"""共有データモデル"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class PaymentMethod(Enum):
    COMPANY_CARD = "COMPANY_CARD"
    PAYPAY = "PayPay"
    CASH = "Cash"
    AMEX = "AMEX"
    VISA = "VISA"
    MASTERCARD = "Mastercard"
    CREDIT_CARD = "CreditCard"  # 汎用、突合が必要
    OTHER = "その他"


class ReceiptSource(Enum):
    UBER = "uber"
    SRIDE = "sride"
    AMAZON = "amazon"


@dataclass
class Receipt:
    source: ReceiptSource
    date: datetime
    amount: int  # JPY
    payment_method: PaymentMethod
    filename: str
    filepath: str
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "source": self.source.value,
            "date": self.date.strftime("%Y-%m-%d %H:%M"),
            "amount": self.amount,
            "payment_method": self.payment_method.value,
            "filename": self.filename,
            "filepath": self.filepath,
            "metadata": self.metadata,
        }
