"""Request/response models for the Orders endpoint group.

``shipping_address`` is a structured object persisted as JSONB. Order-item
prices are a snapshot taken at checkout — they are not the product's current
price. The tracking response is partly synthesized/mock (carrier, estimated
delivery, tracking number) since the schema has no carrier entity.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.order import OrderStatus


class ShippingAddress(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    line1: str = Field(min_length=1, max_length=255)
    line2: str | None = Field(default=None, max_length=255)
    city: str = Field(min_length=1, max_length=128)
    state: str | None = Field(default=None, max_length=128)
    postal_code: str = Field(min_length=1, max_length=32)
    country: str = Field(min_length=2, max_length=64)


class CheckoutRequest(BaseModel):
    shipping_address: ShippingAddress
    coupon_code: str | None = Field(default=None, max_length=50)


class OrderItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    status: OrderStatus
    total_amount: Decimal
    shipping_address: ShippingAddress
    created_at: datetime
    items: list[OrderItemResponse]


class CheckoutResponse(OrderResponse):
    """Checkout returns the created order plus, when Stripe is configured, the
    URL of the hosted payment page to redirect the customer to. ``payment_url``
    is None when payments are not configured (the order is still created)."""

    payment_url: str | None = None


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class TrackingStage(BaseModel):
    status: OrderStatus
    reached: bool
    timestamp: datetime | None = None


class TrackingResponse(BaseModel):
    order_id: uuid.UUID
    status: OrderStatus
    estimated_delivery: datetime | None
    carrier: str | None
    tracking_number: str | None
    timeline: list[TrackingStage]
