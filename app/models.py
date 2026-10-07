from datetime import datetime, timezone

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Tariff(Base):
    __tablename__ = "tariffs"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(unique=True)
    price: Mapped[int]  # копейки


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(default="pending")
    tariff_id: Mapped[int] = mapped_column(ForeignKey("tariffs.id"))
    amount: Mapped[int]  # копейки, уже со скидкой
    discount: Mapped[int]  # копейки
    method: Mapped[str]
    installment_months: Mapped[int | None]
    schedule: Mapped[list[int] | None] = mapped_column(JSON)
    email: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    # unique защищает от дублей на уровне БД; NULL-ов может быть сколько угодно.
    idempotency_key: Mapped[str | None] = mapped_column(unique=True)
