from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator

from app.logic import PROMO_CODE


class TariffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    price: int


class PaymentCreate(BaseModel):
    tariff_id: int
    email: EmailStr
    method: Literal["card", "sbp", "installment"]
    installment_months: Literal[3, 6, 12] | None = None
    promo_code: str | None = None

    @field_validator("promo_code")
    @classmethod
    def check_promo_code(cls, value: str | None) -> str | None:
        if value is not None and value.upper() != PROMO_CODE:
            raise ValueError("unknown promo code")
        return value

    @model_validator(mode="after")
    def check_installment(self) -> "PaymentCreate":
        if self.method == "installment" and self.installment_months is None:
            raise ValueError("installment_months is required for installment")
        if self.method != "installment" and self.installment_months is not None:
            raise ValueError("installment_months must be null for card and sbp")
        return self


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    tariff_id: int
    amount: int
    discount: int
    method: str
    installment_months: int | None
    schedule: list[int] | None
    email: str
    created_at: datetime


class BankWebhook(BaseModel):
    payment_id: int
    status: Literal["succeeded", "failed", "refunded"]
