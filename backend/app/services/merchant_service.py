"""Merchant self-service analytics: dashboard, product listing, revenue summary.

Revenue recognition rule (a business decision): only orders in the
``delivered`` status count toward revenue. Per-merchant revenue is summed from
``order_items`` (``unit_price`` x ``quantity``) for the merchant's own products;
coupons are applied at the order level and are deliberately *not* attributed to
individual merchants (documented simplification).

Order listing is not implemented here — ``GET /merchant/orders`` reuses the
visibility-aware ``order_service.list_orders`` (a merchant already sees exactly
the orders containing their products), with an optional status filter.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderStatus
from app.models.order_item import OrderItem
from app.models.product import Product, ProductStatus
from app.models.user import User
from app.schemas.merchant import (
    LowStockProduct,
    MerchantDashboard,
    RevenueSummary,
    RevenueWindows,
    TopProduct,
)

_LOW_STOCK_THRESHOLD = 10
_TOP_PRODUCTS_LIMIT = 5
_ZERO = Decimal("0.00")


def _merchant_delivered_line_revenue():
    """Base scalar select: SUM(unit_price * quantity) over a merchant's delivered lines.

    Callers add the ``merchant_id`` (and optional ``created_at`` window) filters.
    """
    return (
        select(func.coalesce(func.sum(OrderItem.unit_price * OrderItem.quantity), 0))
        .select_from(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Product, OrderItem.product_id == Product.id)
        .where(Order.status == OrderStatus.DELIVERED)
    )


async def _revenue_since(
    db: AsyncSession, merchant_id: uuid.UUID, since: datetime | None
) -> Decimal:
    stmt = _merchant_delivered_line_revenue().where(Product.merchant_id == merchant_id)
    if since is not None:
        stmt = stmt.where(Order.created_at >= since)
    return Decimal(await db.scalar(stmt))


async def _revenue_windows(db: AsyncSession, merchant_id: uuid.UUID) -> RevenueWindows:
    now = datetime.now(UTC)
    return RevenueWindows(
        last_7_days=await _revenue_since(db, merchant_id, now - timedelta(days=7)),
        last_30_days=await _revenue_since(db, merchant_id, now - timedelta(days=30)),
        last_90_days=await _revenue_since(db, merchant_id, now - timedelta(days=90)),
        all_time=await _revenue_since(db, merchant_id, None),
    )


async def _orders_by_status(db: AsyncSession, merchant_id: uuid.UUID) -> dict[str, int]:
    merchant_order_ids = (
        select(OrderItem.order_id)
        .join(Product, OrderItem.product_id == Product.id)
        .where(Product.merchant_id == merchant_id)
    )
    rows = await db.execute(
        select(Order.status, func.count(Order.id))
        .where(Order.id.in_(merchant_order_ids))
        .group_by(Order.status)
    )
    counts = {status.value: 0 for status in OrderStatus}
    for status, count in rows:
        counts[status.value] = count
    return counts


async def _top_products(db: AsyncSession, merchant_id: uuid.UUID) -> list[TopProduct]:
    units = func.sum(OrderItem.quantity)
    revenue = func.sum(OrderItem.unit_price * OrderItem.quantity)
    rows = await db.execute(
        select(Product.id, Product.title, units.label("units"), revenue.label("revenue"))
        .select_from(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Product, OrderItem.product_id == Product.id)
        .where(Product.merchant_id == merchant_id, Order.status == OrderStatus.DELIVERED)
        .group_by(Product.id, Product.title)
        .order_by(units.desc())
        .limit(_TOP_PRODUCTS_LIMIT)
    )
    return [
        TopProduct(
            product_id=row.id,
            title=row.title,
            units_sold=int(row.units),
            revenue=Decimal(row.revenue),
        )
        for row in rows
    ]


async def _low_stock(db: AsyncSession, merchant_id: uuid.UUID) -> list[LowStockProduct]:
    rows = await db.scalars(
        select(Product)
        .where(
            Product.merchant_id == merchant_id,
            Product.deleted_at.is_(None),
            Product.status == ProductStatus.ACTIVE,
            Product.stock_qty < _LOW_STOCK_THRESHOLD,
        )
        .order_by(Product.stock_qty, Product.id)
    )
    return [LowStockProduct(product_id=p.id, title=p.title, stock_qty=p.stock_qty) for p in rows]


async def _product_count(db: AsyncSession, merchant_id: uuid.UUID) -> int:
    return await db.scalar(
        select(func.count(Product.id)).where(
            Product.merchant_id == merchant_id, Product.deleted_at.is_(None)
        )
    )


async def dashboard(db: AsyncSession, *, merchant: User) -> MerchantDashboard:
    return MerchantDashboard(
        revenue=await _revenue_windows(db, merchant.id),
        orders_by_status=await _orders_by_status(db, merchant.id),
        top_products=await _top_products(db, merchant.id),
        low_stock=await _low_stock(db, merchant.id),
        product_count=await _product_count(db, merchant.id),
    )


async def revenue_summary(db: AsyncSession, *, merchant: User) -> RevenueSummary:
    windows = await _revenue_windows(db, merchant.id)
    delivered_order_count = await db.scalar(
        select(func.count(func.distinct(Order.id)))
        .select_from(Order)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .join(Product, OrderItem.product_id == Product.id)
        .where(Product.merchant_id == merchant.id, Order.status == OrderStatus.DELIVERED)
    )
    if delivered_order_count:
        aov = (windows.all_time / delivered_order_count).quantize(Decimal("0.01"))
    else:
        aov = _ZERO
    return RevenueSummary(
        total_revenue=windows.all_time,
        delivered_order_count=delivered_order_count,
        average_order_value=aov,
        revenue=windows,
    )


async def list_products(
    db: AsyncSession,
    *,
    merchant: User,
    status: ProductStatus | None,
    cursor: str | None,
    limit: int,
) -> tuple[list[Product], str | None]:
    """List the merchant's own products (all statuses, excluding soft-deleted).

    Unlike the public catalog, drafts and archived products are visible here.
    Keyset-paginated by ascending id, matching the public products listing.
    """
    from app.services.product_service import _paginate_by_id  # local: shared keyset helper

    stmt = select(Product).where(Product.merchant_id == merchant.id, Product.deleted_at.is_(None))
    if status is not None:
        stmt = stmt.where(Product.status == status)
    return await _paginate_by_id(db, stmt, cursor=cursor, limit=limit)
