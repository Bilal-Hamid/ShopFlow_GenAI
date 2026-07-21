"""Merchant endpoints (merchant role only).

Read-only analytics and listings scoped to the authenticated merchant:
dashboard snapshot, own-product listing (all statuses), orders containing their
products, and a revenue summary. All routes are rate-limited per authenticated
user. ``GET /merchant/orders`` delegates to the visibility-aware order listing
so a merchant sees exactly the orders that contain their products.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import authenticated_rate_limiter, require_roles
from app.api.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.db.session import get_db
from app.models.order import OrderStatus
from app.models.product import ProductStatus
from app.models.user import User, UserRole
from app.schemas.merchant import MerchantDashboard, RevenueSummary
from app.schemas.order import OrderResponse
from app.schemas.problem import ProblemDetail
from app.schemas.product import ProductResponse
from app.services import merchant_service, order_service

router = APIRouter(
    prefix="/merchant",
    tags=["merchant"],
    dependencies=[Depends(authenticated_rate_limiter)],
    responses={
        403: {"model": ProblemDetail, "description": "Not a merchant"},
        429: {"model": ProblemDetail, "description": "Rate limit exceeded"},
    },
)

DbSession = Annotated[AsyncSession, Depends(get_db)]
Limit = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
MerchantUser = Annotated[User, Depends(require_roles(UserRole.MERCHANT))]


@router.get(
    "/dashboard",
    response_model=MerchantDashboard,
    summary="Merchant dashboard: revenue windows, orders by status, top products, low stock",
)
async def dashboard(db: DbSession, merchant: MerchantUser) -> MerchantDashboard:
    return await merchant_service.dashboard(db, merchant=merchant)


@router.get(
    "/products",
    response_model=Page[ProductResponse],
    summary="List the merchant's own products, all statuses (cursor-paginated)",
)
async def list_products(
    db: DbSession,
    merchant: MerchantUser,
    status: ProductStatus | None = None,
    cursor: str | None = None,
    limit: Limit = DEFAULT_PAGE_SIZE,
) -> Page[ProductResponse]:
    items, next_cursor = await merchant_service.list_products(
        db, merchant=merchant, status=status, cursor=cursor, limit=limit
    )
    return Page(items=items, next_cursor=next_cursor)


@router.get(
    "/orders",
    response_model=Page[OrderResponse],
    summary="List orders containing the merchant's products (cursor-paginated)",
)
async def list_orders(
    db: DbSession,
    merchant: MerchantUser,
    status: OrderStatus | None = None,
    cursor: str | None = None,
    limit: Limit = DEFAULT_PAGE_SIZE,
) -> Page[OrderResponse]:
    items, next_cursor = await order_service.list_orders(
        db, user=merchant, status=status, cursor=cursor, limit=limit
    )
    return Page(items=items, next_cursor=next_cursor)


@router.get(
    "/revenue-summary",
    response_model=RevenueSummary,
    summary="Merchant revenue summary (delivered orders only)",
)
async def revenue_summary(db: DbSession, merchant: MerchantUser) -> RevenueSummary:
    return await merchant_service.revenue_summary(db, merchant=merchant)
