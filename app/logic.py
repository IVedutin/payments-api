PROMO_CODE = "KVITTO10"
PROMO_PERCENT = 10

TARIFFS = {"basic": 990000, "standard": 1990000, "premium": 2990000}

ALLOWED_TRANSITIONS = {
    "pending": {"succeeded", "failed"},
    "succeeded": {"refunded"},
}


def calc_discount(price: int, promo_code: str | None) -> int:
    if promo_code is None:
        return 0
    # Целочисленное деление: копейки скидки округляются вниз, в пользу школы.
    return price * PROMO_PERCENT // 100


def make_schedule(amount: int, months: int) -> list[int]:
    base, remainder = divmod(amount, months)
    # Остаток копеек распределяем по первым платежам.
    return [base + 1 if i < remainder else base for i in range(months)]


def can_transition(current: str, new: str) -> bool:
    return new in ALLOWED_TRANSITIONS.get(current, set())
