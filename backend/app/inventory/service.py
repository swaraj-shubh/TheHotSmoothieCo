"""Inventory operations.

These functions only flush, never commit: the caller owns the transaction, so e.g. checkout can
reserve stock and create the order atomically. Any raised error means the caller must roll back
(the request-scoped session does this automatically).

Concurrency: stock changes are single conditional UPDATEs (`... WHERE on_hand - reserved >= qty`).
Postgres row-locks the row and re-checks the condition after any concurrent writer commits,
so two buyers can never both take the last unit. Multi-variant operations touch rows in sorted
variant_id order so concurrent checkouts can't deadlock each other.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, Conflict, NotFound
from app.core.pagination import Page, decode_cursor, encode_cursor
from app.inventory.models import (
    Inventory,
    InventoryReservation,
    InventoryTransaction,
    ReservationStatus,
    TxnType,
)
from app.inventory.schemas import AdjustIn, StockRow, TransactionOut


class InsufficientInventory(Conflict):
    code, message = "INSUFFICIENT_INVENTORY", "Some items are no longer available in the requested quantity"


class InventoryNotFound(NotFound):
    code, message = "INVENTORY_NOT_FOUND", "No inventory record for this variant"


class InvalidAdjustment(AppError):
    code, message = "INVALID_ADJUSTMENT", "Stock cannot go below the quantity currently reserved"


def _now() -> datetime:
    return datetime.now(UTC)


def _log(
    db: AsyncSession,
    variant_id: uuid.UUID,
    type_: TxnType,
    row: tuple[int, ...],
    *,
    on_hand_delta: int = 0,
    reserved_delta: int = 0,
    reference_id: uuid.UUID | None = None,
    reason: str | None = None,
    actor_id: uuid.UUID | None = None,
) -> None:
    db.add(
        InventoryTransaction(
            variant_id=variant_id,
            type=type_,
            on_hand_delta=on_hand_delta,
            reserved_delta=reserved_delta,
            on_hand_after=row[0],
            reserved_after=row[1],
            reference_id=reference_id,
            reason=reason,
            actor_user_id=actor_id,
        )
    )


async def init_stock(
    db: AsyncSession, variant_id: uuid.UUID, on_hand: int, threshold: int, actor_id: uuid.UUID | None
) -> None:
    db.add(
        Inventory(variant_id=variant_id, on_hand=on_hand, reserved=0, sold=0, low_stock_threshold=threshold)
    )
    _log(db, variant_id, TxnType.INITIAL, (on_hand, 0), on_hand_delta=on_hand, actor_id=actor_id)
    await db.flush()


async def availability(db: AsyncSession, variant_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not variant_ids:
        return {}
    rows = await db.execute(
        select(Inventory.variant_id, Inventory.on_hand - Inventory.reserved).where(
            Inventory.variant_id.in_(variant_ids)
        )
    )
    return {vid: max(avail, 0) for vid, avail in rows.all()}


async def adjust(
    db: AsyncSession,
    variant_id: uuid.UUID,
    *,
    delta: int | None = None,
    set_to: int | None = None,
    reason: str,
    actor_id: uuid.UUID | None,
    type_: TxnType = TxnType.ADJUSTMENT,
) -> Inventory:
    """Staff stock change: relative (`delta`) or absolute (`set_to`, e.g. after a stock count)."""
    inv = await db.scalar(select(Inventory).where(Inventory.variant_id == variant_id).with_for_update())
    if inv is None:
        raise InventoryNotFound()
    change = (set_to - inv.on_hand) if set_to is not None else (delta or 0)
    if inv.on_hand + change < inv.reserved:
        raise InvalidAdjustment(details={"reserved": inv.reserved, "on_hand": inv.on_hand})
    inv.on_hand += change
    _log(
        db,
        variant_id,
        type_,
        (inv.on_hand, inv.reserved),
        on_hand_delta=change,
        reason=reason,
        actor_id=actor_id,
    )
    await db.flush()
    return inv


async def reserve(
    db: AsyncSession, reference_id: uuid.UUID, items: dict[uuid.UUID, int], ttl_seconds: int
) -> list[InventoryReservation]:
    """Hold stock for an order. Idempotent per reference: a retry returns the existing holds.
    All-or-nothing: if any line is short, raises InsufficientInventory listing every short variant."""
    existing = list(
        await db.scalars(
            select(InventoryReservation).where(InventoryReservation.reference_id == reference_id)
        )
    )
    if existing:
        return existing

    short: list[dict] = []
    reservations = []
    expires_at = _now() + timedelta(seconds=ttl_seconds)
    for variant_id, qty in sorted(items.items()):
        if qty <= 0:
            raise AppError("Quantity must be positive", code="INVALID_QUANTITY")
        row = (
            await db.execute(
                update(Inventory)
                .where(Inventory.variant_id == variant_id, Inventory.on_hand - Inventory.reserved >= qty)
                .values(reserved=Inventory.reserved + qty)
                .returning(Inventory.on_hand, Inventory.reserved)
            )
        ).first()
        if row is None:
            short.append({"variant_id": str(variant_id), "requested": qty})
            continue
        _log(db, variant_id, TxnType.RESERVE, tuple(row), reserved_delta=qty, reference_id=reference_id)
        reservation = InventoryReservation(
            reference_id=reference_id, variant_id=variant_id, quantity=qty, expires_at=expires_at
        )
        db.add(reservation)
        reservations.append(reservation)

    if short:
        avail = await availability(db, [uuid.UUID(s["variant_id"]) for s in short])
        for s in short:
            s["available"] = avail.get(uuid.UUID(s["variant_id"]), 0)
        raise InsufficientInventory(details=short)
    await db.flush()
    return reservations


async def _settle(db: AsyncSession, reference_id: uuid.UUID, to: ReservationStatus) -> int:
    """Move a reference's ACTIVE reservations to COMMITTED / RELEASED / EXPIRED.
    Only ACTIVE rows are touched, so repeating the call (duplicate webhook, retried job) is a no-op."""
    rows = list(
        await db.scalars(
            select(InventoryReservation)
            .where(
                InventoryReservation.reference_id == reference_id,
                InventoryReservation.status == ReservationStatus.ACTIVE,
            )
            .order_by(InventoryReservation.variant_id)
            .with_for_update()
        )
    )
    for r in rows:
        if to == ReservationStatus.COMMITTED:
            values = {
                "on_hand": Inventory.on_hand - r.quantity,
                "reserved": Inventory.reserved - r.quantity,
                "sold": Inventory.sold + r.quantity,
            }
            on_hand_delta, txn = -r.quantity, TxnType.COMMIT
        else:
            values = {"reserved": Inventory.reserved - r.quantity}
            on_hand_delta, txn = 0, TxnType.RELEASE
        row = (
            await db.execute(
                update(Inventory)
                .where(Inventory.variant_id == r.variant_id)
                .values(**values)
                .returning(Inventory.on_hand, Inventory.reserved)
            )
        ).one()
        _log(
            db,
            r.variant_id,
            txn,
            tuple(row),
            on_hand_delta=on_hand_delta,
            reserved_delta=-r.quantity,
            reference_id=reference_id,
            reason=None if to == ReservationStatus.COMMITTED else to.lower(),
        )
        r.status = to
    await db.flush()
    return len(rows)


async def commit_reservation(db: AsyncSession, reference_id: uuid.UUID) -> int:
    """Payment confirmed: reserved units become sold. Returns lines committed (0 = already done
    or the hold had been released — the payment flow must handle that case)."""
    return await _settle(db, reference_id, ReservationStatus.COMMITTED)


async def release_reservation(db: AsyncSession, reference_id: uuid.UUID, *, expired: bool = False) -> int:
    return await _settle(
        db, reference_id, ReservationStatus.EXPIRED if expired else ReservationStatus.RELEASED
    )


async def expired_references(db: AsyncSession, limit: int = 100) -> list[uuid.UUID]:
    """References with overdue holds. SKIP LOCKED lets several sweeper workers run safely in parallel."""
    refs = await db.scalars(
        select(InventoryReservation.reference_id)
        .where(
            InventoryReservation.status == ReservationStatus.ACTIVE,
            InventoryReservation.expires_at < _now(),
        )
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return list(dict.fromkeys(refs))  # one order holds several rows; DISTINCT can't combine with FOR UPDATE


async def return_to_stock(
    db: AsyncSession, variant_id: uuid.UUID, qty: int, reference_id: uuid.UUID, actor_id: uuid.UUID | None
) -> Inventory:
    return await adjust(
        db, variant_id, delta=qty, reason=f"return {reference_id}", actor_id=actor_id, type_=TxnType.RETURN
    )


# ---------- Admin reads ----------


async def stock_list(
    db: AsyncSession, *, low_stock_only: bool, q: str | None, cursor: str | None, limit: int
) -> Page[StockRow]:
    # Local import: catalog depends on inventory, not the other way round, except for this read model.
    from app.catalog.models import Product, ProductVariant

    available = Inventory.on_hand - Inventory.reserved
    stmt = (
        select(Inventory, ProductVariant.sku, ProductVariant.title, Product.id, Product.title)
        .join(ProductVariant, ProductVariant.id == Inventory.variant_id)
        .join(Product, Product.id == ProductVariant.product_id)
    )
    if low_stock_only:
        stmt = stmt.where(available <= Inventory.low_stock_threshold, ProductVariant.is_active.is_(True))
    if q:
        stmt = stmt.where(ProductVariant.sku.ilike(f"{q.upper().replace('%', '').replace('_', r'\_')}%"))
    if cursor:
        (last_sku,) = decode_cursor(cursor, 1)
        stmt = stmt.where(ProductVariant.sku > last_sku)
    rows = (await db.execute(stmt.order_by(ProductVariant.sku).limit(limit + 1))).all()
    items = [
        StockRow(
            variant_id=inv.variant_id,
            sku=sku,
            product_id=pid,
            product_title=ptitle,
            variant_title=vtitle,
            on_hand=inv.on_hand,
            reserved=inv.reserved,
            available=inv.available,
            sold=inv.sold,
            low_stock_threshold=inv.low_stock_threshold,
            low_stock=inv.available <= inv.low_stock_threshold,
        )
        for inv, sku, vtitle, pid, ptitle in rows[:limit]
    ]
    return Page(items=items, next_cursor=encode_cursor(items[-1].sku) if len(rows) > limit else None)


async def history(
    db: AsyncSession, variant_id: uuid.UUID, cursor: str | None, limit: int
) -> Page[TransactionOut]:
    stmt = select(InventoryTransaction).where(InventoryTransaction.variant_id == variant_id)
    if cursor:
        ts, tid = decode_cursor(cursor, 2)
        stmt = stmt.where(
            tuple_(InventoryTransaction.created_at, InventoryTransaction.id)
            < (datetime.fromisoformat(ts), uuid.UUID(tid))
        )
    rows = list(
        await db.scalars(
            stmt.order_by(InventoryTransaction.created_at.desc(), InventoryTransaction.id.desc()).limit(
                limit + 1
            )
        )
    )
    items = [TransactionOut.model_validate(r) for r in rows[:limit]]
    nxt = encode_cursor(items[-1].created_at, items[-1].id) if len(rows) > limit else None
    return Page(items=items, next_cursor=nxt)


async def admin_adjust(db: AsyncSession, variant_id: uuid.UUID, data: AdjustIn, actor_id: uuid.UUID) -> None:
    inv = await adjust(
        db, variant_id, delta=data.delta, set_to=data.set_to, reason=data.reason, actor_id=actor_id
    )
    if data.low_stock_threshold is not None:
        inv.low_stock_threshold = data.low_stock_threshold
    await db.commit()
