import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app

STANDARD_ID = 2  # standard = 1990000 копеек


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:  # lifespan создаёт таблицы и тарифы
        yield c


def pay(client, headers=None, **fields):
    body = {"tariff_id": STANDARD_ID, "email": "user@example.com", "method": "card"} | fields
    return client.post("/payments", json=body, headers=headers)


def test_tariffs_in_kopecks(client):
    r = client.get("/tariffs")
    assert r.status_code == 200
    assert r.json() == [
        {"id": 1, "title": "basic", "price": 990000},
        {"id": 2, "title": "standard", "price": 1990000},
        {"id": 3, "title": "premium", "price": 2990000},
    ]


def test_create_payment_without_promo(client):
    r = pay(client)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert body["amount"] == 1990000
    assert body["discount"] == 0
    assert body["schedule"] is None
    assert body["installment_months"] is None


@pytest.mark.parametrize("code", ["KVITTO10", "kvitto10", "KvItTo10"])
def test_promo_code_any_case(client, code):
    r = pay(client, promo_code=code)
    assert r.status_code == 201
    assert r.json()["discount"] == 199000
    assert r.json()["amount"] == 1791000


def test_unknown_promo_code_is_422(client):
    assert pay(client, promo_code="UNKNOWN").status_code == 422


@pytest.mark.parametrize("months", [3, 6, 12])
def test_installment_schedule_sums_to_amount(client, months):
    r = pay(client, method="installment", installment_months=months, promo_code="kvitto10")
    assert r.status_code == 201
    body = r.json()
    assert len(body["schedule"]) == months
    assert sum(body["schedule"]) == body["amount"] == 1791000
    assert max(body["schedule"]) - min(body["schedule"]) <= 1


def test_installment_remainder_goes_to_first_payments(client):
    r = pay(client, method="installment", installment_months=3)
    assert r.json()["schedule"] == [663334, 663333, 663333]


@pytest.mark.parametrize(
    "fields",
    [
        {"method": "installment"},
        {"method": "installment", "installment_months": 5},
        {"method": "card", "installment_months": 3},
    ],
)
def test_invalid_installment_is_422(client, fields):
    assert pay(client, **fields).status_code == 422


def test_idempotency_key_returns_same_payment(client):
    headers = {"Idempotency-Key": "abc123"}
    first = pay(client, headers=headers)
    second = pay(client, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json() == first.json()
    assert client.get("/payments/2").status_code == 404  # второго платежа нет


def test_without_idempotency_key_creates_new_payments(client):
    assert pay(client).json()["id"] == 1
    assert pay(client).json()["id"] == 2


def test_get_payment(client):
    created = pay(client).json()
    r = client.get(f"/payments/{created['id']}")
    assert r.status_code == 200
    assert r.json() == created


def test_unknown_payment_is_404(client):
    assert client.get("/payments/999").status_code == 404
    r = client.post("/webhooks/bank", json={"payment_id": 999, "status": "succeeded"})
    assert r.status_code == 404


def test_unknown_tariff_is_404(client):
    assert pay(client, tariff_id=999).status_code == 404


@pytest.mark.parametrize(
    "path",
    [["succeeded"], ["failed"], ["succeeded", "refunded"]],
)
def test_allowed_transitions(client, path):
    payment_id = pay(client).json()["id"]
    for status in path:
        r = client.post("/webhooks/bank", json={"payment_id": payment_id, "status": status})
        assert r.status_code == 200
        assert r.json() == {"result": "ok"}
    assert client.get(f"/payments/{payment_id}").json()["status"] == path[-1]


@pytest.mark.parametrize(
    "setup, forbidden",
    [
        ([], "refunded"),  # pending -> refunded
        (["succeeded"], "failed"),  # succeeded -> failed
        (["failed"], "succeeded"),  # failed -> succeeded
    ],
)
def test_forbidden_transition_is_409_and_status_unchanged(client, setup, forbidden):
    payment_id = pay(client).json()["id"]
    for status in setup:
        client.post("/webhooks/bank", json={"payment_id": payment_id, "status": status})
    before = client.get(f"/payments/{payment_id}").json()["status"]

    r = client.post("/webhooks/bank", json={"payment_id": payment_id, "status": forbidden})

    assert r.status_code == 409
    assert r.json() == {"error": "invalid_transition"}
    assert client.get(f"/payments/{payment_id}").json()["status"] == before
