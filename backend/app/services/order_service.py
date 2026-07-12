"""Orders business logic: checkout, listing/visibility, status transitions,
tracking.

Checkout is transactional: product rows are locked (``FOR UPDATE``), stock is
validated and decremented, prices are snapshotted into ``order_items``, an
optional coupon is applied, and the Redis cart is cleared — all or nothing.

Visibility: a customer sees their own orders; a merchant sees orders containing
at least one of their products; an admin sees all. A single order may span
multiple merchants and shares one status (a documented simplification).

Status transitions (PATCH):
- merchant: advance forward along pending -> confirmed -> shipped -> delivered
- customer: cancel while still pending or confirmed (restocks the items)
- admin: any transition
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import Select, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ProblemException
from app.api.pagination import InvalidCursorError, decode_cursor, encode_cursor
from app.models.order import Order, OrderStatus
from app.models.order_item import OrderItem
from app.models.product import Product, ProductStatus
from app.models.user import User, UserRole
from app.schemas.order import (
    OrderItemResponse,
    OrderResponse,
    ShippingAddress,
    TrackingResponse,
    TrackingStage,
)
from app.services import cart_service, coupon_service

_FORWARD = [
    OrderStatus.PENDING,
    OrderStatus.CONFIRMED,
    OrderStatus.SHIPPED,
    OrderStatus.DELIVERED,
]
_MOCK_CARRIER = "ShopFlow Logistics"
_MOCK_DELIVERY_DAYS = 7


# --------------------------------------------------------------------------- #
# Response assembly
# --------------------------------------------------------------------------- #
async def _load_items(db: AsyncSession, order_id: uuid.UUID) -> list[OrderItem]:
    return list(
        await db.scalars(
            select(OrderItem).where(OrderItem.order_id == order_id).order_by(OrderItem.id)
        )
    )


def _to_response(order: Order, items: list[OrderItem]) -> OrderResponse:
    return OrderResponse(
        id=order.id,
        customer_id=order.customer_id,
        status=order.status,
        total_amount=order.total_amount,
        shipping_address=order.shipping_address,
        created_at=order.created_at,
        items=[
            OrderItemResponse(
                id=i.id,
                product_id=i.product_id,
                quantity=i.quantity,
                unit_price=i.unit_price,
                line_total=i.unit_price * i.quantity,
            )
            for i in items
        ],
    )


# --------------------------------------------------------------------------- #
# Checkout
# --------------------------------------------------------------------------- #
async def checkout(
    db: AsyncSession,
    *,
    customer: User,
    shipping_address: ShippingAddress,
    coupon_code: str | None,
) -> OrderResponse:
    raw = await cart_service._raw_cart(customer.id)
    if not raw:
        raise ProblemException(
            status_code=422, detail="Your cart is empty.", title="Unprocessable Entity"
        )

    ids = [uuid.UUID(pid) for pid in raw]
    # Lock the product rows for the duration of the transaction to prevent
    # oversell under concurrent checkouts.
    locked = await db.scalars(
        select(Product)
        .where(
            Product.id.in_(ids),
            Product.status == ProductStatus.ACTIVE,
            Product.deleted_at.is_(None),
        )
        .with_for_update()
    )
    products = {p.id: p for p in locked}

    subtotal = Decimal("0.00")
    line_specs: list[tuple[Product, int, Decimal]] = []
    for pid_str, qty_str in raw.items():
        product = products.get(uuid.UUID(pid_str))
        if product is None:
            raise ProblemException(
                status_code=409,
                detail="A product in your cart is no longer available.",
                title="Conflict",
            )
        qty = int(qty_str)
        if qty > product.stock_qty:
            raise ProblemException(
                status_code=409,
                detail=f"Only {product.stock_qty} unit(s) of '{product.title}' are in stock.",
                title="Conflict",
            )
        subtotal += product.price * qty
        line_specs.append((product, qty, product.price))

    coupon = None
    discount = Decimal("0.00")
    if coupon_code:
        coupon = await coupon_service.validate_coupon(db, coupon_code)
        discount = coupon_service.compute_discount(coupon, subtotal)
    total = max(subtotal - discount, Decimal("0.00"))

    if coupon is not None:
        await coupon_service.reserve_usage(coupon)  # raises 409 if exhausted

    try:
        order = Order(
            customer_id=customer.id,
            status=OrderStatus.PENDING,
            total_amount=total,
            shipping_address=shipping_address.model_dump(),
        )
        db.add(order)
        await db.flush()

        items: list[OrderItem] = []
        for product, qty, unit_price in line_specs:
            item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=qty,
                unit_price=unit_price,
            )
            db.add(item)
            items.append(item)
            product.stock_qty -= qty

        await db.commit()
    except Exception:
        await db.rollback()
        if coupon is not None:
            await coupon_service.release_usage(coupon)
        raise

    await cart_service.clear_cart(customer.id)
    for item in items:
        await db.refresh(item)
    await db.refresh(order)
    return _to_response(order, items)


# --------------------------------------------------------------------------- #
# Listing / retrieval with role-based visibility
# --------------------------------------------------------------------------- #
def _visible_orders(user: User) -> Select[tuple[Order]]:
    if user.role == UserRole.ADMIN:
        return select(Order)
    if user.role == UserRole.MERCHANT:
        merchant_order_ids = (
            select(OrderItem.order_id)
            .join(Product, OrderItem.product_id == Product.id)
            .where(Product.merchant_id == user.id)
        )
        return select(Order).where(Order.id.in_(merchant_order_ids))
    return select(Order).where(Order.customer_id == user.id)


async def list_orders(
    db: AsyncSession,
    *,
    user: User,
    cursor: str | None,
    limit: int,
    status: OrderStatus | None = None,
) -> tuple[list[OrderResponse], str | None]:
    stmt = _visible_orders(user)
    if status is not None:
        stmt = stmt.where(Order.status == status)

    if cursor is not None:
        try:
            data = decode_cursor(cursor)
            c_created = datetime.fromisoformat(data["created_at"])
            c_id = uuid.UUID(data["id"])
        except (InvalidCursorError, KeyError, ValueError) as exc:
            raise ProblemException(
                status_code=422,
                detail="Invalid pagination cursor.",
                title="Unprocessable Entity",
            ) from exc
        stmt = stmt.where(tuple_(Order.created_at, Order.id) < tuple_(c_created, c_id))

    stmt = stmt.order_by(Order.created_at.desc(), Order.id.desc()).limit(limit + 1)
    orders = list(await db.scalars(stmt))

    next_cursor = None
    if len(orders) > limit:
        orders = orders[:limit]
        last = orders[-1]
        next_cursor = encode_cursor({"created_at": last.created_at.isoformat(), "id": str(last.id)})

    responses = [_to_response(o, await _load_items(db, o.id)) for o in orders]
    return responses, next_cursor


async def _load_visible_order(db: AsyncSession, order_id: uuid.UUID, user: User) -> Order:
    order = await db.get(Order, order_id)
    if order is None:
        raise _not_found()

    if user.role == UserRole.ADMIN:
        return order
    if user.role == UserRole.CUSTOMER:
        if order.customer_id != user.id:
            raise _not_found()
        return order
    # merchant: must own at least one product in the order
    owns = await db.scalar(
        select(OrderItem.id)
        .join(Product, OrderItem.product_id == Product.id)
        .where(OrderItem.order_id == order.id, Product.merchant_id == user.id)
        .limit(1)
    )
    if owns is None:
        raise _not_found()
    return order


async def get_order(db: AsyncSession, *, order_id: uuid.UUID, user: User) -> OrderResponse:
    order = await _load_visible_order(db, order_id, user)
    return _to_response(order, await _load_items(db, order.id))


# --------------------------------------------------------------------------- #
# Status transitions
# --------------------------------------------------------------------------- #
async def update_status(
    db: AsyncSession, *, order_id: uuid.UUID, user: User, new_status: OrderStatus
) -> OrderResponse:
    order = await _load_visible_order(db, order_id, user)
    current = order.status

    if user.role == UserRole.ADMIN:
        pass  # admins may make any transition
    elif user.role == UserRole.CUSTOMER:
        if new_status != OrderStatus.CANCELLED:
            raise ProblemException(
                status_code=403,
                detail="Customers may only cancel their orders.",
                title="Forbidden",
            )
        if current not in (OrderStatus.PENDING, OrderStatus.CONFIRMED):
            raise ProblemException(
                status_code=409,
                detail=f"An order in '{current.value}' status can no longer be cancelled.",
                title="Conflict",
            )
    else:  # merchant
        if new_status == OrderStatus.CANCELLED:
            raise ProblemException(
                status_code=403,
                detail="Merchants cannot cancel orders.",
                title="Forbidden",
            )
        if (
            current not in _FORWARD
            or new_status not in _FORWARD
            or _FORWARD.index(new_status) <= _FORWARD.index(current)
        ):
            raise ProblemException(
                status_code=409,
                detail=f"Cannot move an order from '{current.value}' to '{new_status.value}'.",
                title="Conflict",
            )

    # Cancelling returns reserved stock to inventory.
    if new_status == OrderStatus.CANCELLED and current != OrderStatus.CANCELLED:
        await _restock_order(db, order.id)

    order.status = new_status
    await db.commit()
    await db.refresh(order)
    return _to_response(order, await _load_items(db, order.id))


async def _restock_order(db: AsyncSession, order_id: uuid.UUID) -> None:
    items = await _load_items(db, order_id)
    if not items:
        return
    product_ids = [i.product_id for i in items]
    products = {
        p.id: p
        for p in await db.scalars(
            select(Product).where(Product.id.in_(product_ids)).with_for_update()
        )
    }
    for item in items:
        product = products.get(item.product_id)
        if product is not None:
            product.stock_qty += item.quantity


# --------------------------------------------------------------------------- #
# Tracking (partly synthesized/mock)
# --------------------------------------------------------------------------- #
async def get_tracking(db: AsyncSession, *, order_id: uuid.UUID, user: User) -> TrackingResponse:
    order = await _load_visible_order(db, order_id, user)

    if order.status == OrderStatus.CANCELLED:
        timeline = [
            TrackingStage(status=OrderStatus.PENDING, reached=True, timestamp=order.created_at),
            TrackingStage(status=OrderStatus.CANCELLED, reached=True, timestamp=None),
        ]
        estimated_delivery = None
        carrier = None
        tracking_number = None
    else:
        current_index = _FORWARD.index(order.status)
        timeline = [
            TrackingStage(
                status=stage,
                reached=index <= current_index,
                timestamp=order.created_at if index == 0 else None,
            )
            for index, stage in enumerate(_FORWARD)
        ]
        estimated_delivery = order.created_at + timedelta(days=_MOCK_DELIVERY_DAYS)
        carrier = _MOCK_CARRIER
        tracking_number = f"SF-{order.id.hex[:12].upper()}"

    return TrackingResponse(
        order_id=order.id,
        status=order.status,
        estimated_delivery=estimated_delivery,
        carrier=carrier,
        tracking_number=tracking_number,
        timeline=timeline,
    )


def _not_found() -> ProblemException:
    return ProblemException(status_code=404, detail="Order not found.", title="Not Found")
