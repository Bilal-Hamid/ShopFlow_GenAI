"""Shared request dependencies: authentication and role-based access control.

``get_current_user`` resolves the caller from the access-token cookie and loads
the (non-deleted) user. ``require_roles(...)`` builds a dependency that enforces
RBAC for the three roles — every protected route in later endpoint groups must
depend on it rather than checking roles ad hoc.
"""

import uuid
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cookies import ACCESS_COOKIE_NAME
from app.api.errors import ProblemException
from app.api.rate_limit import RateLimiter
from app.core.config import settings
from app.core.security import ACCESS_TOKEN_TYPE, TokenError, decode_token
from app.db.session import get_db
from app.models.user import User, UserRole


def _unauthorized(detail: str) -> ProblemException:
    return ProblemException(
        status_code=401,
        detail=detail,
        title="Unauthorized",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    token = request.cookies.get(ACCESS_COOKIE_NAME)
    if not token:
        raise _unauthorized("Not authenticated.")

    try:
        claims = decode_token(token, expected_type=ACCESS_TOKEN_TYPE)
        user_id = uuid.UUID(claims["sub"])
    except (TokenError, KeyError, ValueError) as exc:
        raise _unauthorized("Invalid or expired token.") from exc

    user = await db.scalar(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    if user is None:
        raise _unauthorized("User no longer exists.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(
    *roles: UserRole,
) -> Callable[[User], Coroutine[Any, Any, User]]:
    """Dependency factory enforcing that the current user has one of ``roles``."""

    async def _dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ProblemException(
                status_code=403,
                detail="You do not have permission to perform this action.",
                title="Forbidden",
            )
        return user

    return _dependency


# Authenticated rate limiter: 1000/min per user id. Reused by protected routes.
authenticated_rate_limiter = RateLimiter(
    limit=settings.rate_limit_authenticated_per_minute,
    scope="user",
    identifier=lambda request: _authenticated_identifier(request),
)


async def _authenticated_identifier(request: Request) -> str:
    """Best-effort user id from the access cookie, falling back to client IP."""
    token = request.cookies.get(ACCESS_COOKIE_NAME)
    if token:
        try:
            return decode_token(token, expected_type=ACCESS_TOKEN_TYPE)["sub"]
        except TokenError, KeyError:
            pass
    return request.client.host if request.client else "unknown"
