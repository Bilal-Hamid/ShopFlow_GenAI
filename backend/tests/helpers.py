"""Shared test helpers for the product/cart/order/review endpoint tests.

Users are created directly (admins can't self-register), and products/coupons
are inserted straight into the DB so each test can set up exactly the catalog it
needs. ``logged_in_client`` yields an ``AsyncClient`` with auth cookies for the
given user, so a single test can drive multiple roles via separate clients.
"""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal

from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.category import Category
from app.models.coupon import Coupon, DiscountType
from app.models.product import Product, ProductStatus
from app.models.user import User, UserRole

DEFAULT_PASSWORD = "abcd1234"


async def make_user(email: str, role: UserRole, password: str = DEFAULT_PASSWORD) -> User:
    async with AsyncSessionLocal() as session:
        user = User(email=email, password_hash=hash_password(password), role=role)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def make_product(
    *,
    merchant_id: uuid.UUID,
    title: str = "Widget",
    price: str = "10.00",
    stock_qty: int = 100,
    status: ProductStatus = ProductStatus.ACTIVE,
    category_id: uuid.UUID | None = None,
    description: str | None = "A fine widget",
) -> Product:
    async with AsyncSessionLocal() as session:
        product = Product(
            merchant_id=merchant_id,
            title=title,
            description=description,
            price=Decimal(price),
            stock_qty=stock_qty,
            status=status,
            category_id=category_id,
            images=[],
        )
        session.add(product)
        await session.commit()
        await session.refresh(product)
        return product


async def make_category(name: str = "Home", slug: str = "home") -> Category:
    async with AsyncSessionLocal() as session:
        category = Category(name=name, slug=slug)
        session.add(category)
        await session.commit()
        await session.refresh(category)
        return category


async def make_coupon(
    *,
    code: str,
    discount_type: DiscountType,
    value: str,
    usage_limit: int | None = None,
    expires_at: datetime | None = None,
) -> Coupon:
    async with AsyncSessionLocal() as session:
        coupon = Coupon(
            code=code,
            discount_type=discount_type,
            value=Decimal(value),
            usage_limit=usage_limit,
            expires_at=expires_at,
        )
        session.add(coupon)
        await session.commit()
        await session.refresh(coupon)
        return coupon


@asynccontextmanager
async def logged_in_client(email: str, password: str = DEFAULT_PASSWORD):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/auth/login", json={"email": email, "password": password})
        assert resp.status_code == 200, resp.text
        yield ac
