"""Products endpoints: public catalog reads + merchant-scoped writes.

Read routes (list, search, detail) are public and rate-limited per IP; write
routes require an authenticated merchant (or admin) and are rate-limited per
user. Ownership of the mutated product is enforced in the service layer.
"""

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import authenticated_rate_limiter, require_roles
from app.api.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.api.rate_limit import public_rate_limiter
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.problem import ProblemDetail
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.services import product_service

router = APIRouter(prefix="/products", tags=["products"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
Limit = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]

# Merchants own products; admins may act on any. Ownership enforced in service.
MerchantUser = Annotated[User, Depends(require_roles(UserRole.MERCHANT))]
MerchantOrAdmin = Annotated[User, Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN))]

_PUBLIC = [Depends(public_rate_limiter)]
_AUTH = [Depends(authenticated_rate_limiter)]


@router.get(
    "",
    response_model=Page[ProductResponse],
    summary="List active products (cursor-paginated)",
    dependencies=_PUBLIC,
)
async def list_products(
    db: DbSession,
    cursor: str | None = None,
    limit: Limit = DEFAULT_PAGE_SIZE,
) -> Page[ProductResponse]:
    items, next_cursor = await product_service.list_products(db, cursor=cursor, limit=limit)
    return Page(items=items, next_cursor=next_cursor)


@router.get(
    "/search",
    response_model=Page[ProductResponse],
    summary="Search active products by text and filters",
    dependencies=_PUBLIC,
)
async def search_products(
    db: DbSession,
    q: Annotated[
        str | None, Query(description="Case-insensitive match on title/description")
    ] = None,
    category_id: uuid.UUID | None = None,
    min_price: Annotated[Decimal | None, Query(ge=0)] = None,
    max_price: Annotated[Decimal | None, Query(ge=0)] = None,
    cursor: str | None = None,
    limit: Limit = DEFAULT_PAGE_SIZE,
) -> Page[ProductResponse]:
    items, next_cursor = await product_service.search_products(
        db,
        query=q,
        category_id=category_id,
        min_price=min_price,
        max_price=max_price,
        cursor=cursor,
        limit=limit,
    )
    return Page(items=items, next_cursor=next_cursor)


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Get a single active product",
    dependencies=_PUBLIC,
    responses={404: {"model": ProblemDetail, "description": "Product not found"}},
)
async def get_product(product_id: uuid.UUID, db: DbSession) -> ProductResponse:
    return await product_service.get_visible_product(db, product_id)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ProductResponse,
    summary="Create a product (merchant)",
    dependencies=_AUTH,
    responses={
        403: {"model": ProblemDetail, "description": "Not a merchant"},
        422: {"model": ProblemDetail, "description": "Validation error"},
    },
)
async def create_product(
    payload: ProductCreate, db: DbSession, merchant: MerchantUser
) -> ProductResponse:
    return await product_service.create_product(db, merchant=merchant, data=payload)


@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Update a product (owning merchant or admin)",
    dependencies=_AUTH,
    responses={
        403: {"model": ProblemDetail, "description": "Not the owner"},
        404: {"model": ProblemDetail, "description": "Product not found"},
    },
)
async def update_product(
    product_id: uuid.UUID, payload: ProductUpdate, db: DbSession, user: MerchantOrAdmin
) -> ProductResponse:
    return await product_service.update_product(db, product_id=product_id, user=user, data=payload)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a product (owning merchant or admin)",
    dependencies=_AUTH,
    responses={
        403: {"model": ProblemDetail, "description": "Not the owner"},
        404: {"model": ProblemDetail, "description": "Product not found"},
    },
)
async def delete_product(product_id: uuid.UUID, db: DbSession, user: MerchantOrAdmin) -> Response:
    await product_service.soft_delete_product(db, product_id=product_id, user=user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
