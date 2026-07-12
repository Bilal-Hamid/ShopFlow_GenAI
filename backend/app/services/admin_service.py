"""Admin business logic: user management and platform-wide statistics.

``update_user`` doubles as a recovery flow — an admin can reset a target user's
email/password, change their role, and deactivate/reactivate them. Guardrails:

- An admin cannot demote or deactivate **themselves** (prevents accidental
  self-lockout).
- The **last active admin** cannot be demoted or deactivated (prevents locking
  the platform out of all admin access).
- A new email must be globally unique (the column is unique including
  soft-deleted rows), else 409.
- Passwords are validated (schema) and Argon2-hashed here; plaintext never hits
  the DB.

KNOWN LIMITATION (deliberate, per product decision): changing a user's email or
password does **not** revoke their existing sessions. Refresh-token families are
keyed only by family id with no user->family index, and access tokens are
stateless 15-minute JWTs, so outstanding sessions remain valid until they expire
naturally. Revisit if this endpoint is used for compromise recovery.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ProblemException
from app.api.pagination import InvalidCursorError, decode_cursor, encode_cursor
from app.core.security import hash_password
from app.models.order import Order, OrderStatus
from app.models.product import Product, ProductStatus
from app.models.user import User, UserRole
from app.schemas.admin import AdminUserUpdate, PlatformStats
from app.schemas.merchant import RevenueWindows


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #
async def list_users(
    db: AsyncSession,
    *,
    role: UserRole | None,
    include_deleted: bool,
    cursor: str | None,
    limit: int,
) -> tuple[list[User], str | None]:
    """List users, newest first. Soft-deleted rows are excluded unless requested."""
    stmt = select(User)
    if not include_deleted:
        stmt = stmt.where(User.deleted_at.is_(None))
    if role is not None:
        stmt = stmt.where(User.role == role)

    if cursor is not None:
        try:
            data = decode_cursor(cursor)
            c_created = datetime.fromisoformat(data["created_at"])
            c_id = uuid.UUID(data["id"])
        except (InvalidCursorError, KeyError, ValueError) as exc:
            raise ProblemException(
                status_code=422,
                detail="Invalid pagination cursor.",
                title="Unprocessable Entity",
            ) from exc
        stmt = stmt.where(tuple_(User.created_at, User.id) < tuple_(c_created, c_id))

    stmt = stmt.order_by(User.created_at.desc(), User.id.desc()).limit(limit + 1)
    users = list(await db.scalars(stmt))

    next_cursor = None
    if len(users) > limit:
        users = users[:limit]
        last = users[-1]
        next_cursor = encode_cursor({"created_at": last.created_at.isoformat(), "id": str(last.id)})
    return users, next_cursor


async def _active_admin_count(db: AsyncSession) -> int:
    return await db.scalar(
        select(func.count(User.id)).where(User.role == UserRole.ADMIN, User.deleted_at.is_(None))
    )


async def update_user(
    db: AsyncSession, *, actor: User, user_id: uuid.UUID, data: AdminUserUpdate
) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise ProblemException(status_code=404, detail="User not found.", title="Not Found")

    is_self = user.id == actor.id
    losing_admin_rights = user.role == UserRole.ADMIN and (
        (data.role is not None and data.role != UserRole.ADMIN)
        or (data.is_active is False and user.deleted_at is None)
    )

    # --- Guardrails -------------------------------------------------------- #
    # Primary protection: an admin may not strip their own admin rights. Because
    # the caller is always an active admin (auth + RBAC), this alone guarantees
    # at least one admin always remains.
    if is_self and losing_admin_rights:
        raise ProblemException(
            status_code=403,
            detail="Admins cannot demote or deactivate their own account.",
            title="Forbidden",
        )
    # Defensive backstop: never let the last active admin lose their rights.
    # (Unreachable while the self-guard above holds, but kept so the invariant
    # survives if that guard is ever relaxed.)
    if losing_admin_rights and await _active_admin_count(db) <= 1:
        raise ProblemException(
            status_code=409,
            detail="Cannot demote or deactivate the last active admin.",
            title="Conflict",
        )

    # --- Mutations --------------------------------------------------------- #
    if data.email is not None:
        normalized = data.email.strip().lower()
        if normalized != user.email:
            clash = await db.scalar(
                select(User.id).where(User.email == normalized, User.id != user.id)
            )
            if clash is not None:
                raise ProblemException(
                    status_code=409,
                    detail="Another account already uses this email.",
                    title="Conflict",
                )
            user.email = normalized

    if data.password is not None:
        user.password_hash = hash_password(data.password)
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.deleted_at = None if data.is_active else datetime.now(UTC)

    await db.commit()
    await db.refresh(user)
    return user


# --------------------------------------------------------------------------- #
# Platform statistics
# --------------------------------------------------------------------------- #
async def _count_by(db: AsyncSession, column, keys, *, where=None) -> dict[str, int]:
    """Group-count ``column`` and return a dict zero-filled over ``keys`` (StrEnum).

    ``where`` optionally restricts the population (e.g. exclude soft-deleted rows).
    """
    stmt = select(column, func.count()).group_by(column)
    if where is not None:
        stmt = stmt.where(where)
    rows = await db.execute(stmt)
    counts = {key.value: 0 for key in keys}
    for value, count in rows:
        counts[value.value] = count
    return counts


async def _platform_revenue_since(db: AsyncSession, since: datetime | None) -> Decimal:
    stmt = select(func.coalesce(func.sum(Order.total_amount), 0)).where(
        Order.status == OrderStatus.DELIVERED
    )
    if since is not None:
        stmt = stmt.where(Order.created_at >= since)
    return Decimal(await db.scalar(stmt))


async def platform_stats(db: AsyncSession) -> PlatformStats:
    now = datetime.now(UTC)
    # Users and products are soft-deletable; count only live rows. Orders are
    # hard-deleted, so every row is live.
    users_by_role = await _count_by(db, User.role, UserRole, where=User.deleted_at.is_(None))
    products_by_status = await _count_by(
        db, Product.status, ProductStatus, where=Product.deleted_at.is_(None)
    )
    orders_by_status = await _count_by(db, Order.status, OrderStatus)

    return PlatformStats(
        total_users=sum(users_by_role.values()),
        users_by_role=users_by_role,
        total_products=sum(products_by_status.values()),
        products_by_status=products_by_status,
        total_orders=sum(orders_by_status.values()),
        orders_by_status=orders_by_status,
        total_revenue=await _platform_revenue_since(db, None),
        revenue=RevenueWindows(
            last_7_days=await _platform_revenue_since(db, now - timedelta(days=7)),
            last_30_days=await _platform_revenue_since(db, now - timedelta(days=30)),
            last_90_days=await _platform_revenue_since(db, now - timedelta(days=90)),
            all_time=await _platform_revenue_since(db, None),
        ),
    )
