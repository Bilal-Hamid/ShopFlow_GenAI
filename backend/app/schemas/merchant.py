"""Response models for the Merchant analytics endpoint group.

All figures recognise revenue only for orders in the ``delivered`` status.
Per-merchant revenue is summed from ``order_items`` (``unit_price`` x
``quantity``) for the merchant's own products; because coupons are applied at
the order level, the coupon discount is intentionally not attributed to
individual merchants (a documented simplification). ``orders_by_status`` always
carries a key for every ``OrderStatus`` (zero-filled) so the frontend donut has
a stable shape.
"""

import uuid
from decimal import Decimal

from pydantic import BaseModel


class RevenueWindows(BaseModel):
    """Revenue rolled up over trailing time windows plus an all-time total."""

    last_7_days: Decimal
    last_30_days: Decimal
    last_90_days: Decimal
    all_time: Decimal


class TopProduct(BaseModel):
    product_id: uuid.UUID
    title: str
    units_sold: int
    revenue: Decimal


class LowStockProduct(BaseModel):
    product_id: uuid.UUID
    title: str
    stock_qty: int


class MerchantDashboard(BaseModel):
    revenue: RevenueWindows
    orders_by_status: dict[str, int]
    top_products: list[TopProduct]
    low_stock: list[LowStockProduct]
    product_count: int


class RevenueSummary(BaseModel):
    total_revenue: Decimal
    delivered_order_count: int
    average_order_value: Decimal
    revenue: RevenueWindows
