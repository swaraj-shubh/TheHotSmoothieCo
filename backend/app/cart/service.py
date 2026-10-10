import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.cart.models import Cart, CartItem
from app.cart.schemas import CartItemOut, CartOut, LineIssue, TotalsOut
from app.catalog import repository as catalog
from app.checkout import pricing
from app.core.config import get_settings
from app.core.exceptions import AppError, NotFound
from app.core.security import hash_token, new_opaque_token
from app.coupons import service as coupons
from app.inventory.service import InsufficientInventory
from app.notifications import service as notifications
from app.orders.models import Order
from app.users.models import User

MAX_SHOWN = 20  # cap on what the storefront reveals about stock


class CartNotFound(NotFound):
    code, message = "CART_NOT_FOUND", "Cart not found"


class CartItemNotFound(NotFound):
    code, message = "CART_ITEM_NOT_FOUND", "Item not in cart"


class VariantUnavailable(AppError):
    code, message = "VARIANT_UNAVAILABLE", "This item is not available"


class CartFull(AppError):
    code, message = "CART_FULL", "Your cart has too many different items"


# ---------- Locating the cart ----------


async def _user_cart(db: AsyncSession, user_id: uuid.UUID, create: bool) -> Cart | None:
    cart = await db.scalar(select(Cart).where(Cart.user_id == user_id))
    if cart or not create:
        return cart
    # Concurrent first requests from one user: the partial unique index lets only one insert win.
    await db.execute(insert(Cart).values(id=uuid.uuid4(), user_id=user_id).on_conflict_do_nothing())
    return await db.scalar(select(Cart).where(Cart.user_id == user_id))


async def _guest_cart(db: AsyncSession, token: str | None) -> Cart | None:
    if not token or len(token) > 256:
        return None
    return await db.scalar(
        select(Cart).where(Cart.guest_token_hash == hash_token(token), Cart.user_id.is_(None))
    )


async def get_cart(
    db: AsyncSession, user_id: uuid.UUID | None, guest_token: str | None, *, create: bool = False
) -> tuple[Cart | None, str | None]:
    """Returns (cart, new_guest_token). A logged-in user always gets their own cart; the guest
    token is only used for /cart/merge."""
    if user_id:
        return await _user_cart(db, user_id, create), None
    cart = await _guest_cart(db, guest_token)
    if cart or not create:
        return cart, None
    token = new_opaque_token()
    cart = Cart(guest_token_hash=hash_token(token), items=[])
    db.add(cart)
    await db.flush()
    return cart, token


# ---------- Pricing the cart ----------


async def build_lines(
    db: AsyncSession, items: list[CartItem]
) -> tuple[list[CartItemOut], list[pricing.Line]]:
    info = await catalog.purchasables(db, [i.variant_id for i in items])
    out, lines = [], []
    for item in items:
        p = info[item.variant_id]
        issue = None
        if not p.is_purchasable:
            issue = LineIssue.UNAVAILABLE
        elif item.quantity > p.available:
            issue = LineIssue.INSUFFICIENT_STOCK
        out.append(
            CartItemOut(
                id=item.id,
                variant_id=p.variant_id,
                product_id=p.product_id,
                product_slug=p.product_slug,
                product_title=p.product_title,
                variant_title=p.variant_title,
                sku=p.sku,
                attributes=p.attributes,
                image_url=p.image_url,
                unit_price_paise=p.price_paise,  # always the live catalog price
                compare_at_price_paise=p.compare_at_price_paise,
                quantity=item.quantity,
                line_total_paise=p.price_paise * item.quantity,
                max_purchasable=min(p.available, MAX_SHOWN) if p.is_purchasable else 0,
                issue=issue,
            )
        )
        if issue != LineIssue.UNAVAILABLE:
            lines.append(
                pricing.Line(p.variant_id, p.product_id, p.category_id, p.price_paise, item.quantity)
            )
    return out, lines


def totals(lines: list[pricing.Line], coupon_terms: pricing.CouponTerms | None) -> pricing.Totals:
    s = get_settings()
    return pricing.compute_totals(
        lines,
        coupon_terms,
        shipping_flat=s.shipping_flat_paise,
        free_shipping_threshold=s.free_shipping_threshold_paise,
        tax_rate_bps=s.tax_rate_bps,
        prices_include_tax=s.prices_include_tax,
    )


async def view(
    db: AsyncSession, cart: Cart | None, user_id: uuid.UUID | None, token: str | None = None
) -> CartOut:
    items = cart.items if cart else []
    out, lines = await build_lines(db, items)
    coupon_terms, coupon_error = None, None
    if cart and cart.coupon_code and lines:
        try:
            _, coupon_terms = await coupons.validate(db, cart.coupon_code, user_id, lines)
        except coupons.InvalidCoupon as exc:
            coupon_error = exc.message  # shown to the customer; the code stays until they remove it
    t = totals(lines, coupon_terms)
    return CartOut(
        id=cart.id if cart else None,
        items=out,
        item_count=sum(i.quantity for i in out),
        coupon_code=cart.coupon_code if cart else None,
        coupon_error=coupon_error,
        totals=TotalsOut(
            subtotal_paise=t.subtotal_paise,
            discount_paise=t.discount_paise,
            shipping_paise=t.shipping_paise,
            tax_paise=t.tax_paise,
            total_paise=t.total_paise,
            prices_include_tax=get_settings().prices_include_tax,
        ),
        checkout_ready=bool(out) and all(i.issue is None for i in out) and coupon_error is None,
        cart_token=token,
    )


async def _reload(db: AsyncSession, cart: Cart) -> Cart:
    await db.refresh(cart, ["items"])
    return cart


# ---------- Mutations ----------


async def add_item(db: AsyncSession, cart: Cart, variant_id: uuid.UUID, quantity: int) -> Cart:
    s = get_settings()
    p = (await catalog.purchasables(db, [variant_id])).get(variant_id)
    if p is None or not p.is_purchasable:
        raise VariantUnavailable()
    lines = await db.scalar(select(func.count()).where(CartItem.cart_id == cart.id)) or 0
    if lines >= s.max_cart_lines and not any(i.variant_id == variant_id for i in cart.items):
        raise CartFull()

    # Atomic upsert: two tabs adding the same poster add up instead of colliding.
    new_qty = await db.scalar(
        insert(CartItem)
        .values(
            id=uuid.uuid4(),
            cart_id=cart.id,
            variant_id=variant_id,
            quantity=min(quantity, s.max_cart_item_quantity),
        )
        .on_conflict_do_update(
            index_elements=["cart_id", "variant_id"],
            set_={
                "quantity": func.least(CartItem.quantity + quantity, s.max_cart_item_quantity),
                "updated_at": func.now(),
            },
        )
        .returning(CartItem.quantity)
    )
    if (new_qty or 0) > p.available:  # soft check; the real guarantee is the reservation at checkout
        raise InsufficientInventory(
            details=[{"variant_id": str(variant_id), "requested": new_qty, "available": p.available}]
        )
    await db.commit()
    return await _reload(db, cart)


async def _item(db: AsyncSession, cart: Cart, item_id: uuid.UUID) -> CartItem:
    item = await db.scalar(select(CartItem).where(CartItem.id == item_id, CartItem.cart_id == cart.id))
    if item is None:
        raise CartItemNotFound()
    return item


async def update_item(db: AsyncSession, cart: Cart, item_id: uuid.UUID, quantity: int) -> Cart:
    item = await _item(db, cart, item_id)
    p = (await catalog.purchasables(db, [item.variant_id]))[item.variant_id]
    quantity = min(quantity, get_settings().max_cart_item_quantity)
    if quantity > item.quantity and quantity > p.available:  # decreasing is always allowed
        raise InsufficientInventory(
            details=[{"variant_id": str(item.variant_id), "requested": quantity, "available": p.available}]
        )
    item.quantity = quantity
    await db.commit()
    return await _reload(db, cart)


async def remove_item(db: AsyncSession, cart: Cart, item_id: uuid.UUID) -> Cart:
    await db.delete(await _item(db, cart, item_id))
    await db.commit()
    return await _reload(db, cart)


async def clear(db: AsyncSession, cart: Cart) -> Cart:
    await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    cart.coupon_code = None
    await db.commit()
    return await _reload(db, cart)


async def apply_coupon(db: AsyncSession, cart: Cart, user_id: uuid.UUID | None, code: str) -> Cart:
    _, lines = await build_lines(db, cart.items)
    if not lines:
        raise coupons.InvalidCoupon("Add something to your cart first")
    await coupons.validate(db, code, user_id, lines)  # raises with the reason
    cart.coupon_code = code.upper()  # one code per cart: stacking is impossible by construction
    await db.commit()
    return cart


async def remove_coupon(db: AsyncSession, cart: Cart) -> Cart:
    cart.coupon_code = None
    await db.commit()
    return cart


async def merge_guest_cart(db: AsyncSession, user_id: uuid.UUID, guest_token: str | None) -> Cart:
    """After login: fold the guest cart into the user's cart, then delete it. Safe to repeat."""
    user_cart = await _user_cart(db, user_id, create=True)
    assert user_cart is not None
    guest = await _guest_cart(db, guest_token)
    if guest:
        max_qty = get_settings().max_cart_item_quantity
        for item in guest.items:
            await db.execute(
                insert(CartItem)
                .values(
                    id=uuid.uuid4(),
                    cart_id=user_cart.id,
                    variant_id=item.variant_id,
                    quantity=min(item.quantity, max_qty),
                )
                .on_conflict_do_update(
                    index_elements=["cart_id", "variant_id"],
                    set_={"quantity": func.least(CartItem.quantity + item.quantity, max_qty)},
                )
            )
        user_cart.coupon_code = user_cart.coupon_code or guest.coupon_code
        await db.delete(guest)
    await db.commit()
    return await _reload(db, user_cart)


async def clear_after_order(db: AsyncSession, user_id: uuid.UUID, variant_ids: list[uuid.UUID]) -> None:
    """Remove purchased lines once payment succeeds (no commit: part of the payment transaction)."""
    cart = await _user_cart(db, user_id, create=False)
    if cart:
        await db.execute(
            delete(CartItem).where(CartItem.cart_id == cart.id, CartItem.variant_id.in_(variant_ids))
        )
        cart.coupon_code = None


# ---------- Background jobs ----------


async def queue_abandoned_cart_reminders(db: AsyncSession, limit: int = 200) -> int:
    """One reminder per stretch of cart activity, 24–72h after the last change, only for signed-in
    customers who haven't ordered since. Opt-outs are honoured at send time (marketing template)."""
    now = datetime.now(UTC)
    last = (
        select(
            CartItem.cart_id,
            func.max(CartItem.updated_at).label("last"),
            func.sum(CartItem.quantity).label("qty"),
        )
        .group_by(CartItem.cart_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(Cart, User, last.c.last, last.c.qty)
            .join(last, last.c.cart_id == Cart.id)
            .join(User, User.id == Cart.user_id)
            .where(
                User.is_active.is_(True),
                User.deleted_at.is_(None),
                last.c.last.between(now - timedelta(hours=72), now - timedelta(hours=24)),
                (Cart.abandoned_notified_at.is_(None)) | (Cart.abandoned_notified_at < last.c.last),
                ~select(Order.id)
                .where(Order.user_id == Cart.user_id, Order.created_at > last.c.last)
                .exists(),
            )
            .limit(limit)
            .with_for_update(of=Cart, skip_locked=True)
        )
    ).all()
    s = get_settings()
    for cart, user, last_at, qty in rows:
        await notifications.enqueue(
            db,
            "abandoned_cart",
            recipient=user.email,
            user_id=user.id,
            context={
                "name": user.full_name.split(" ")[0],
                "item_count": qty,
                "cart_url": f"{s.frontend_url}/cart",
            },
            dedupe_key=f"abandoned_cart:{cart.id}:{last_at.isoformat()}",
        )
        cart.abandoned_notified_at = now
    await db.commit()
    return len(rows)


async def delete_stale_guest_carts(db: AsyncSession, days: int = 30) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    recent_item = (
        select(CartItem.id).where(CartItem.cart_id == Cart.id, CartItem.updated_at >= cutoff).exists()
    )
    result = await db.execute(
        delete(Cart).where(Cart.user_id.is_(None), Cart.updated_at < cutoff, ~recent_item)
    )
    await db.commit()
    return result.rowcount  # type: ignore[attr-defined]
