"""Request/response models for the Products endpoint group.

Money is a ``Decimal`` capped at the DB's ``Numeric(10, 2)`` precision. Writes
never accept ``merchant_id`` from the client — it is always the authenticated
merchant. Status defaults to ``draft`` on create (matching the model default).
"""

import uuid
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.product import ProductStatus

Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]
Title = Annotated[str, Field(min_length=1, max_length=255)]


class ProductCreate(BaseModel):
    title: Title
    description: str | None = None
    price: Money
    stock_qty: int = Field(default=0, ge=0)
    category_id: uuid.UUID | None = None
    images: list[str] = Field(default_factory=list)
    status: ProductStatus = ProductStatus.DRAFT


class ProductUpdate(BaseModel):
    """PATCH — every field optional; only provided fields are applied."""

    title: Title | None = None
    description: str | None = None
    price: Money | None = None
    stock_qty: int | None = Field(default=None, ge=0)
    category_id: uuid.UUID | None = None
    images: list[str] | None = None
    status: ProductStatus | None = None


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    merchant_id: uuid.UUID
    title: str
    description: str | None
    price: Decimal
    stock_qty: int
    category_id: uuid.UUID | None
    images: list[str]
    status: ProductStatus
