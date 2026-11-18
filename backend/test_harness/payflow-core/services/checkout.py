"""Checkout calculations with class-method edges and several decision points."""

from services.payments import authorize_payment, validate_currency


def checkout_total(items: list[dict]) -> int:
    total = 0
    for item in items:
        price = item["price_cents"]
        quantity = item.get("quantity", 1)
        if type(price) is not int or type(quantity) is not int:
            raise ValueError("Prices and quantities must be integers")
        if price < 0 or quantity < 1:
            raise ValueError("Price must be non-negative and quantity positive")
        total += price * quantity
    return total


def apply_discount(total_cents: int, discount_cents: int = 0) -> int:
    if discount_cents < 0 or discount_cents > total_cents:
        raise ValueError("Discount must be within the total")
    return total_cents - discount_cents


class CheckoutService:
    """Explicit self._validate call exercises probable-edge resolution."""

    def _validate(self, items: list[dict], currency: str) -> None:
        if not items:
            raise ValueError("Checkout requires at least one item")
        validate_currency(currency)

    def charge(self, items: list[dict], currency: str = "USD") -> dict:
        self._validate(items, currency)
        return authorize_payment(checkout_total(items), currency)
