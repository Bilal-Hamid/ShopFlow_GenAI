"""Orders endpoints (authenticated).

Checkout is customer-only. Listing/retrieval/tracking are open to any
authenticated user but filtered by role-based visibility in the service
(customer=own, merchant=orders with their products, admin=all). Status-update
permissions are enforced per role in the service. All routes are rate-limited
per authenticated user.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, authenticated_rate_limiter, require_roles
from app.api.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.order import (
    CheckoutRequest,
    OrderResponse,
    OrderStatusUpdate,
    TrackingResponse,
)
from app.schemas.problem import ProblemDetail
from app.services import order_service

router = APIRouter(
    prefix="/orders",
    tags=["orders"],
    dependencies=[Depends(authenticated_rate_limiter)],
    responses={429: {"model": ProblemDetail, "description": "Rate limit exceeded"}},
)

DbSession = Annotated[AsyncSession, Depends(get_db)]
Limit = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
CustomerUser = Annotated[User, Depends(require_roles(UserRole.CUSTOMER))]


@router.post(
    "/checkout",
    status_code=201,
    response_model=OrderResponse,
    summary="Check out the cart into an order (customer)",
    responses={
        403: {"model": ProblemDetail, "description": "Not a customer"},
        409: {"model": ProblemDetail, "description": "Stock or coupon conflict"},
        422: {"model": ProblemDetail, "description": "Empty cart or invalid coupon"},
    },
)
async def checkout(
    payload: CheckoutRequest, db: DbSession, customer: CustomerUser
) -> OrderResponse:
    return await order_service.checkout(
        db,
        customer=customer,
        shipping_address=payload.shipping_address,
        coupon_code=payload.coupon_code,
    )


@router.get(
    "",
    response_model=Page[OrderResponse],
    summary="List orders visible to the caller (cursor-paginated)",
)
async def list_orders(
    db: DbSession,
    user: CurrentUser,
    cursor: str | None = None,
    limit: Limit = DEFAULT_PAGE_SIZE,
) -> Page[OrderResponse]:
    items, next_cursor = await order_service.list_orders(db, user=user, cursor=cursor, limit=limit)
    return Page(items=items, next_cursor=next_cursor)


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Get a single order",
    responses={404: {"model": ProblemDetail, "description": "Order not found"}},
)
async def get_order(order_id: uuid.UUID, db: DbSession, user: CurrentUser) -> OrderResponse:
    return await order_service.get_order(db, order_id=order_id, user=user)


@router.patch(
    "/{order_id}/status",
    response_model=OrderResponse,
    summary="Update an order's status",
    responses={
        403: {"model": ProblemDetail, "description": "Transition not allowed for role"},
        404: {"model": ProblemDetail, "description": "Order not found"},
        409: {"model": ProblemDetail, "description": "Invalid status transition"},
    },
)
async def update_status(
    order_id: uuid.UUID, payload: OrderStatusUpdate, db: DbSession, user: CurrentUser
) -> OrderResponse:
    return await order_service.update_status(
        db, order_id=order_id, user=user, new_status=payload.status
    )


@router.get(
    "/{order_id}/tracking",
    response_model=TrackingResponse,
    summary="Get order tracking (carrier/ETA are mock data)",
    responses={404: {"model": ProblemDetail, "description": "Order not found"}},
)
async def get_tracking(order_id: uuid.UUID, db: DbSession, user: CurrentUser) -> TrackingResponse:
    return await order_service.get_tracking(db, order_id=order_id, user=user)
