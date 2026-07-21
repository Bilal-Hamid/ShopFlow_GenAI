"""Products business logic: catalog reads, search, and merchant CRUD.

Read paths (list/search/detail) surface only ``active``, non-deleted products —
merchant drafts/archived are reached through the merchant endpoint group. Writes
are owner-scoped: a merchant may only mutate products whose ``merchant_id`` is
their own; admins may mutate any. Deletion is soft (``deleted_at``), never a hard
DELETE (standards requirement).
"""

import uuid
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ProblemException
from app.api.pagination import InvalidCursorError, decode_cursor, encode_cursor
from app.models.category import Category
from app.models.product import Product, ProductStatus
from app.models.user import User, UserRole
from app.schemas.product import ProductCreate, ProductUpdate


def _visible() -> Select[tuple[Product]]:
    """Base query for publicly visible products (active, not soft-deleted)."""
    return select(Product).where(
        Product.status == ProductStatus.ACTIVE,
        Product.deleted_at.is_(None),
    )


async def _paginate_by_id(
    db: AsyncSession, stmt: Select[tuple[Product]], *, cursor: str | None, limit: int
) -> tuple[list[Product], str | None]:
    """Keyset-paginate a product query by ascending ``id``."""
    if cursor is not None:
        try:
            last_id = uuid.UUID(decode_cursor(cursor)["id"])
        except (InvalidCursorError, KeyError, ValueError) as exc:
            raise ProblemException(
                status_code=422,
                detail="Invalid pagination cursor.",
                title="Unprocessable Entity",
            ) from exc
        stmt = stmt.where(Product.id > last_id)

    stmt = stmt.order_by(Product.id).limit(limit + 1)
    rows = list(await db.scalars(stmt))

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor({"id": str(rows[-1].id)})
    return rows, next_cursor


async def list_products(
    db: AsyncSession, *, cursor: str | None, limit: int
) -> tuple[list[Product], str | None]:
    return await _paginate_by_id(db, _visible(), cursor=cursor, limit=limit)


async def search_products(
    db: AsyncSession,
    *,
    query: str | None,
    category_id: uuid.UUID | None,
    min_price: Decimal | None,
    max_price: Decimal | None,
    cursor: str | None,
    limit: int,
) -> tuple[list[Product], str | None]:
    stmt = _visible()
    if query:
        pattern = f"%{query}%"
        stmt = stmt.where(Product.title.ilike(pattern) | Product.description.ilike(pattern))
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)
    return await _paginate_by_id(db, stmt, cursor=cursor, limit=limit)


async def get_visible_product(db: AsyncSession, product_id: uuid.UUID) -> Product:
    product = await db.scalar(_visible().where(Product.id == product_id))
    if product is None:
        raise _not_found()
    return product


async def _validate_category(db: AsyncSession, category_id: uuid.UUID | None) -> None:
    if category_id is None:
        return
    exists = await db.scalar(select(Category.id).where(Category.id == category_id))
    if exists is None:
        raise ProblemException(
            status_code=422,
            detail="The specified category does not exist.",
            title="Unprocessable Entity",
        )


async def create_product(db: AsyncSession, *, merchant: User, data: ProductCreate) -> Product:
    await _validate_category(db, data.category_id)
    product = Product(
        merchant_id=merchant.id,
        title=data.title,
        description=data.description,
        price=data.price,
        stock_qty=data.stock_qty,
        category_id=data.category_id,
        images=data.images,
        status=data.status,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


async def _load_owned(db: AsyncSession, product_id: uuid.UUID, user: User) -> Product:
    """Load a non-deleted product the ``user`` is allowed to mutate (owner/admin)."""
    product = await db.scalar(
        select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
    )
    if product is None:
        raise _not_found()
    if user.role != UserRole.ADMIN and product.merchant_id != user.id:
        raise ProblemException(
            status_code=403,
            detail="You do not have permission to modify this product.",
            title="Forbidden",
        )
    return product


async def update_product(
    db: AsyncSession, *, product_id: uuid.UUID, user: User, data: ProductUpdate
) -> Product:
    product = await _load_owned(db, product_id, user)

    fields = data.model_dump(exclude_unset=True)
    if "category_id" in fields:
        await _validate_category(db, fields["category_id"])
    for key, value in fields.items():
        setattr(product, key, value)

    await db.commit()
    await db.refresh(product)
    return product


async def soft_delete_product(db: AsyncSession, *, product_id: uuid.UUID, user: User) -> None:
    from datetime import UTC, datetime

    product = await _load_owned(db, product_id, user)
    product.deleted_at = datetime.now(UTC)
    await db.commit()


def _not_found() -> ProblemException:
    return ProblemException(
        status_code=404,
        detail="Product not found.",
        title="Not Found",
    )
