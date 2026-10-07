from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine, get_db
from app.logic import TARIFFS, calc_discount, can_transition, make_schedule
from app.models import Payment, Tariff
from app.schemas import BankWebhook, PaymentCreate, PaymentOut, TariffOut


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        existing = set(db.scalars(select(Tariff.title)))
        db.add_all(Tariff(title=t, price=p) for t, p in TARIFFS.items() if t not in existing)
        db.commit()
    yield


app = FastAPI(title="School Payments API", lifespan=lifespan)


def find_by_key(db: Session, key: str | None) -> Payment | None:
    if key is None:
        return None
    return db.scalar(select(Payment).where(Payment.idempotency_key == key))


@app.get("/tariffs", response_model=list[TariffOut])
def list_tariffs(db: Session = Depends(get_db)):
    return db.scalars(select(Tariff).order_by(Tariff.id)).all()


@app.post("/payments", response_model=PaymentOut, status_code=201)
def create_payment(
    data: PaymentCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if existing := find_by_key(db, idempotency_key):
        response.status_code = 200
        return existing

    tariff = db.get(Tariff, data.tariff_id)
    if tariff is None:
        raise HTTPException(404, "tariff not found")

    discount = calc_discount(tariff.price, data.promo_code)
    amount = tariff.price - discount
    payment = Payment(
        tariff_id=tariff.id,
        amount=amount,
        discount=discount,
        method=data.method,
        installment_months=data.installment_months,
        schedule=make_schedule(amount, data.installment_months) if data.installment_months else None,
        email=data.email,
        idempotency_key=idempotency_key,
    )
    db.add(payment)
    try:
        db.commit()
    except IntegrityError:
        # Параллельный запрос с тем же ключом успел вставить платёж раньше нас.
        db.rollback()
        response.status_code = 200
        return find_by_key(db, idempotency_key)
    db.refresh(payment)
    return payment


@app.get("/payments/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: int, db: Session = Depends(get_db)):
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(404, "payment not found")
    return payment


@app.post("/webhooks/bank")
def bank_webhook(data: BankWebhook, db: Session = Depends(get_db)):
    payment = db.get(Payment, data.payment_id)
    if payment is None:
        raise HTTPException(404, "payment not found")
    if not can_transition(payment.status, data.status):
        return JSONResponse(status_code=409, content={"error": "invalid_transition"})
    payment.status = data.status
    db.commit()
    return {"result": "ok"}
