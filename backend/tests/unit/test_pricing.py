import uuid

import pytest

from app.checkout.pricing import CouponNotApplicable, CouponTerms, Line, compute_totals, discount_for, tax_for

POSTERS, STICKERS = uuid.uuid4(), uuid.uuid4()


def line(price, qty=1, category=POSTERS):
    return Line(uuid.uuid4(), uuid.uuid4(), category, price, qty)


def totals(lines, coupon=None, inclusive=True):
    return compute_totals(
        lines,
        coupon,
        shipping_flat=9900,
        free_shipping_threshold=99900,
        tax_rate_bps=1800,
        prices_include_tax=inclusive,
    )


def test_no_coupon_with_shipping_and_inclusive_tax():
    t = totals([line(50000)])
    assert (t.subtotal_paise, t.discount_paise, t.shipping_paise, t.total_paise) == (50000, 0, 9900, 59900)
    assert t.tax_paise == 7627  # 50000 * 18/118, already inside the price


def test_free_shipping_threshold_uses_discounted_amount():
    assert totals([line(100000)]).shipping_paise == 0
    fixed = CouponTerms("FIXED", 5000)
    assert totals([line(100000)], fixed).shipping_paise == 9900  # 95000 after discount


def test_exclusive_tax_is_added():
    t = totals([line(100000)], inclusive=False)
    assert (t.tax_paise, t.total_paise) == (18000, 118000)


def test_percent_discount_floors_and_caps():
    assert sum(discount_for(CouponTerms("PERCENT", 15), [line(33333)]).values()) == 4999
    capped = CouponTerms("PERCENT", 50, max_discount_paise=10000)
    assert sum(discount_for(capped, [line(100000)]).values()) == 10000


def test_fixed_discount_never_exceeds_total():
    t = totals([line(3000)], CouponTerms("FIXED", 50000))
    assert t.discount_paise == 3000 and t.total_paise >= 0


def test_min_subtotal():
    with pytest.raises(CouponNotApplicable, match="more"):
        discount_for(CouponTerms("FIXED", 100, min_subtotal_paise=50000), [line(49999)])


def test_category_restriction_and_proportional_split_sums_exactly():
    a, b, c = line(10000, 3), line(7001), line(9999, category=STICKERS)
    alloc = discount_for(CouponTerms("PERCENT", 10, category_ids=frozenset({POSTERS})), [a, b, c])
    assert c.variant_id not in alloc  # stickers excluded
    assert sum(alloc.values()) == (30000 + 7001) // 10
    assert all(v <= ln.total for ln in (a, b) for k, v in alloc.items() if k == ln.variant_id)


def test_restricted_coupon_with_no_eligible_items():
    with pytest.raises(CouponNotApplicable, match="doesn't apply"):
        discount_for(CouponTerms("FIXED", 100, product_ids=frozenset({uuid.uuid4()})), [line(5000)])


def test_empty_cart_has_no_shipping():
    assert totals([]).total_paise == 0


def test_tax_rounding():
    assert tax_for(118, rate_bps=1800, inclusive=True) == 18
    assert tax_for(1, rate_bps=1800, inclusive=False) == 0
