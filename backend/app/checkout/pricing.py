"""Pure pricing maths. No I/O, so it's exhaustively unit-tested and shared by cart preview and checkout.

All amounts are integer paise. Percentage discounts floor to whole paise; caps apply after.
"""

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Line:
    variant_id: uuid.UUID
    product_id: uuid.UUID
    category_id: uuid.UUID | None
    unit_price_paise: int
    quantity: int

    @property
    def total(self) -> int:
        return self.unit_price_paise * self.quantity


@dataclass(frozen=True)
class CouponTerms:
    discount_type: str  # "PERCENT" | "FIXED"
    value: int  # percent (1-100) or paise
    max_discount_paise: int | None = None
    min_subtotal_paise: int = 0
    product_ids: frozenset[uuid.UUID] = frozenset()
    category_ids: frozenset[uuid.UUID] = frozenset()

    def applies_to(self, line: Line) -> bool:
        if not self.product_ids and not self.category_ids:
            return True
        return line.product_id in self.product_ids or line.category_id in self.category_ids


@dataclass
class Totals:
    subtotal_paise: int
    discount_paise: int
    shipping_paise: int
    tax_paise: int  # GST portion; included in total when prices are tax-inclusive
    total_paise: int
    line_discounts: dict[uuid.UUID, int] = field(default_factory=dict)  # variant_id -> paise


class CouponNotApplicable(Exception):
    def __init__(self, reason: str):
        self.reason = reason


def discount_for(terms: CouponTerms, lines: list[Line]) -> dict[uuid.UUID, int]:
    """Per-line discount allocation. Never exceeds an eligible line's own total, so totals can't go
    negative. Allocation per line matters later for partial refunds."""
    subtotal = sum(line.total for line in lines)
    if subtotal < terms.min_subtotal_paise:
        raise CouponNotApplicable(
            f"Add items worth ₹{(terms.min_subtotal_paise - subtotal) / 100:.2f} more to use this coupon"
        )
    eligible = [line for line in lines if terms.applies_to(line)]
    eligible_total = sum(line.total for line in eligible)
    if eligible_total == 0:
        raise CouponNotApplicable("This coupon doesn't apply to the items in your cart")

    if terms.discount_type == "PERCENT":
        discount = eligible_total * terms.value // 100
    else:
        discount = terms.value
    if terms.max_discount_paise is not None:
        discount = min(discount, terms.max_discount_paise)
    discount = min(discount, eligible_total)

    # Proportional split; the remainder goes to the largest line so the parts sum exactly.
    alloc = {line.variant_id: discount * line.total // eligible_total for line in eligible}
    largest = max(eligible, key=lambda line: line.total).variant_id
    alloc[largest] += discount - sum(alloc.values())
    return {k: v for k, v in alloc.items() if v}


def shipping_for(amount_after_discount: int, *, flat: int, free_threshold: int) -> int:
    return 0 if amount_after_discount >= free_threshold or amount_after_discount == 0 else flat


def tax_for(amount: int, *, rate_bps: int, inclusive: bool) -> int:
    if inclusive:  # tax already inside the price: extract it
        return round(amount * rate_bps / (10_000 + rate_bps))
    return round(amount * rate_bps / 10_000)


def compute_totals(
    lines: list[Line],
    coupon: CouponTerms | None,
    *,
    shipping_flat: int,
    free_shipping_threshold: int,
    tax_rate_bps: int,
    prices_include_tax: bool,
) -> Totals:
    subtotal = sum(line.total for line in lines)
    line_discounts = discount_for(coupon, lines) if coupon else {}
    discount = sum(line_discounts.values())
    goods = subtotal - discount
    shipping = shipping_for(goods, flat=shipping_flat, free_threshold=free_shipping_threshold)
    # ponytail: GST charged on goods only; shipping GST treatment depends on the registered
    # business setup — revisit with the accountant before going live.
    tax = tax_for(goods, rate_bps=tax_rate_bps, inclusive=prices_include_tax)
    total = goods + shipping + (0 if prices_include_tax else tax)
    return Totals(subtotal, discount, shipping, tax, total, line_discounts)
