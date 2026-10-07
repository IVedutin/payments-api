# School Payments API

API платежей для онлайн-школы: FastAPI + SQLAlchemy + SQLite. Все суммы в **копейках** (`int`).

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Тарифы (`basic`, `standard`, `premium`) создаются при старте. Swagger: http://localhost:8000/docs

## Тесты

```bash
pytest
```

## Примеры

```bash
curl localhost:8000/tariffs

curl -X POST localhost:8000/payments \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: abc123' \
  -d '{"tariff_id": 2, "email": "user@example.com", "method": "installment", "installment_months": 3, "promo_code": "KVITTO10"}'

curl localhost:8000/payments/1

curl -X POST localhost:8000/webhooks/bank \
  -H 'Content-Type: application/json' \
  -d '{"payment_id": 1, "status": "succeeded"}'
```

## Решения

- **Скидка** `price * 10 // 100` — только целые числа; дробные копейки округляются вниз.
- **График рассрочки**: `divmod(amount, months)`, остаток по копейке уходит в первые платежи, поэтому `sum(schedule) == amount`.
- **Idempotency-Key**: сначала ищем платёж по ключу (вернём его с 200). Защиту от гонки даёт `UNIQUE` на `idempotency_key`: второй параллельный INSERT падает с `IntegrityError`, и мы возвращаем уже созданный платёж.
- **Статусы**: словарь `ALLOWED_TRANSITIONS` в `app/logic.py`; запрещённый переход → 409 `{"error": "invalid_transition"}`, в БД ничего не меняется.
- **Неизвестный промокод** проверяется валидатором Pydantic → стандартная 422.
