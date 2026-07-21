"""Cart business logic backed by Redis (ephemeral, per-user).

Storage model: one Redis hash per user, ``cart:{user_id}``, mapping
``product_id -> quantity``. The hash is given a rolling TTL so abandoned carts
expire. There is no cart entity in the database by design (the PRD's data model
omits it); the cart is session-like state, which is what Redis is for here.

Reads enrich each line with live product data and prune any line whose product
is no longer purchasable (soft-deleted or not ``active``), so a cart never shows
a stale/unavailable item. Quantities are validated against current stock on
add/update.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ProblemException
from app.db.redis import redis_client
from app.models.product import Product, ProductStatus
from app.schemas.cart import CartItemResponse, CartResponse

CART_TTL_SECONDS = 7 * 24 * 60 * 60


def _cart_key(user_id: uuid.UUID) -> str:
    return f"cart:{user_id}"


async def _raw_cart(user_id: uuid.UUID) -> dict[str, str]:
    return await redis_client.hgetall(_cart_key(user_id))


async def _load_purchasable(db: AsyncSession, product_id: uuid.UUID) -> Product:
    """Load an active, non-deleted product or raise 404."""
    product = await db.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.status == ProductStatus.ACTIVE,
            Product.deleted_at.is_(None),
        )
    )
    if product is None:
        raise ProblemException(status_code=404, detail="Product not found.", title="Not Found")
    return product


def _check_stock(product: Product, quantity: int) -> None:
    if quantity > product.stock_qty:
        raise ProblemException(
            status_code=409,
            detail=(f"Only {product.stock_qty} unit(s) of '{product.title}' are in stock."),
            title="Conflict",
        )


async def add_item(
    db: AsyncSession, *, user_id: uuid.UUID, product_id: uuid.UUID, quantity: int
) -> CartResponse:
    product = await _load_purchasable(db, product_id)

    key = _cart_key(user_id)
    existing = await redis_client.hget(key, str(product_id))
    new_qty = (int(existing) if existing else 0) + quantity
    _check_stock(product, new_qty)

    await redis_client.hset(key, str(product_id), str(new_qty))
    await redis_client.expire(key, CART_TTL_SECONDS)
    return await get_cart(db, user_id=user_id)


async def update_item(
    db: AsyncSession, *, user_id: uuid.UUID, product_id: uuid.UUID, quantity: int
) -> CartResponse:
    key = _cart_key(user_id)
    if not await redis_client.hexists(key, str(product_id)):
        raise ProblemException(status_code=404, detail="Item not in cart.", title="Not Found")

    product = await _load_purchasable(db, product_id)
    _check_stock(product, quantity)

    await redis_client.hset(key, str(product_id), str(quantity))
    await redis_client.expire(key, CART_TTL_SECONDS)
    return await get_cart(db, user_id=user_id)


async def remove_item(
    db: AsyncSession, *, user_id: uuid.UUID, product_id: uuid.UUID
) -> CartResponse:
    removed = await redis_client.hdel(_cart_key(user_id), str(product_id))
    if removed == 0:
        raise ProblemException(status_code=404, detail="Item not in cart.", title="Not Found")
    return await get_cart(db, user_id=user_id)


async def clear_cart(user_id: uuid.UUID) -> None:
    await redis_client.delete(_cart_key(user_id))


async def get_cart(db: AsyncSession, *, user_id: uuid.UUID) -> CartResponse:
    raw = await _raw_cart(user_id)
    if not raw:
        return CartResponse(items=[], item_count=0, subtotal=Decimal("0.00"))

    ids = [uuid.UUID(pid) for pid in raw]
    products = await db.scalars(
        select(Product).where(
            Product.id.in_(ids),
            Product.status == ProductStatus.ACTIVE,
            Product.deleted_at.is_(None),
        )
    )
    by_id = {p.id: p for p in products}

    items: list[CartItemResponse] = []
    subtotal = Decimal("0.00")
    stale: list[str] = []
    for pid_str, qty_str in raw.items():
        pid = uuid.UUID(pid_str)
        product = by_id.get(pid)
        if product is None:
            stale.append(pid_str)
            continue
        qty = int(qty_str)
        line_total = product.price * qty
        subtotal += line_total
        items.append(
            CartItemResponse(
                product_id=pid,
                title=product.title,
                unit_price=product.price,
                quantity=qty,
                line_total=line_total,
                stock_qty=product.stock_qty,
            )
        )

    # Prune lines whose product is no longer purchasable so the cart self-heals.
    if stale:
        await redis_client.hdel(_cart_key(user_id), *stale)

    items.sort(key=lambda i: str(i.product_id))
    return CartResponse(
        items=items,
        item_count=sum(i.quantity for i in items),
        subtotal=subtotal,
    )
