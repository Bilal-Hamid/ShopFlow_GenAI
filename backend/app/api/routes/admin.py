"""Admin endpoints (admin role only).

User administration (list + update-as-recovery-flow), platform-wide order
listing, and aggregate platform statistics. All routes are rate-limited per
authenticated user. See ``app/services/admin_service.py`` for the guardrails
enforced on user updates (self / last-admin protection) and the documented
session-invalidation limitation.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import authenticated_rate_limiter, require_roles
from app.api.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.db.session import get_db
from app.models.order import OrderStatus
from app.models.user import User, UserRole
from app.schemas.admin import AdminUserResponse, AdminUserUpdate, PlatformStats
from app.schemas.order import OrderResponse
from app.schemas.problem import ProblemDetail
from app.services import admin_service, order_service

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(authenticated_rate_limiter)],
    responses={
        403: {"model": ProblemDetail, "description": "Not an admin"},
        429: {"model": ProblemDetail, "description": "Rate limit exceeded"},
    },
)

DbSession = Annotated[AsyncSession, Depends(get_db)]
Limit = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]


@router.get(
    "/users",
    response_model=Page[AdminUserResponse],
    summary="List users (cursor-paginated, newest first)",
)
async def list_users(
    db: DbSession,
    _admin: AdminUser,
    role: UserRole | None = None,
    include_deleted: bool = False,
    cursor: str | None = None,
    limit: Limit = DEFAULT_PAGE_SIZE,
) -> Page[AdminUserResponse]:
    items, next_cursor = await admin_service.list_users(
        db, role=role, include_deleted=include_deleted, cursor=cursor, limit=limit
    )
    return Page(items=items, next_cursor=next_cursor)


@router.patch(
    "/users/{user_id}",
    response_model=AdminUserResponse,
    summary="Update a user (email/password/role/active) — recovery flow",
    responses={
        403: {"model": ProblemDetail, "description": "Cannot demote/deactivate self"},
        404: {"model": ProblemDetail, "description": "User not found"},
        409: {"model": ProblemDetail, "description": "Email in use or last-admin conflict"},
    },
)
async def update_user(
    user_id: uuid.UUID, payload: AdminUserUpdate, db: DbSession, admin: AdminUser
) -> AdminUserResponse:
    return await admin_service.update_user(db, actor=admin, user_id=user_id, data=payload)


@router.get(
    "/orders",
    response_model=Page[OrderResponse],
    summary="List all orders across the platform (cursor-paginated)",
)
async def list_orders(
    db: DbSession,
    admin: AdminUser,
    status: OrderStatus | None = None,
    cursor: str | None = None,
    limit: Limit = DEFAULT_PAGE_SIZE,
) -> Page[OrderResponse]:
    items, next_cursor = await order_service.list_orders(
        db, user=admin, status=status, cursor=cursor, limit=limit
    )
    return Page(items=items, next_cursor=next_cursor)


@router.get(
    "/platform-stats",
    response_model=PlatformStats,
    summary="Platform-wide statistics (users, products, orders, revenue)",
)
async def platform_stats(db: DbSession, _admin: AdminUser) -> PlatformStats:
    return await admin_service.platform_stats(db)
