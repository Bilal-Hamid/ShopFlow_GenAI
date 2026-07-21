"""Request/response models for the Cart endpoint group.

The cart itself lives in Redis (ephemeral, per-user); these models describe the
HTTP surface. ``CartItemResponse`` is enriched with live product data (title,
current price, available stock) at read time — the cart stores only product id
and quantity.
"""

import uuid
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

Quantity = Annotated[int, Field(ge=1, le=1000)]


class CartItemAdd(BaseModel):
    product_id: uuid.UUID
    quantity: Quantity = 1


class CartItemUpdate(BaseModel):
    quantity: Quantity


class CartItemResponse(BaseModel):
    product_id: uuid.UUID
    title: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal
    stock_qty: int


class CartResponse(BaseModel):
    items: list[CartItemResponse]
    item_count: int
    subtotal: Decimal
