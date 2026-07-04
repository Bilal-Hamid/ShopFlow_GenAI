"""Auth endpoints: register, login, refresh, logout.

All routes are public (no auth required to reach them) but rate-limited at
100 req/min per IP via the router-level ``public_rate_limiter`` dependency.
Access and refresh tokens are delivered exclusively through httpOnly cookies.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cookies import clear_auth_cookies, set_auth_cookies
from app.api.errors import ProblemException
from app.api.rate_limit import public_rate_limiter
from app.core.security import (
    REFRESH_TOKEN_TYPE,
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, RegisterRequest, UserResponse
from app.schemas.problem import ProblemDetail
from app.services import token_store
from app.services.auth_service import authenticate_user, register_user

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    dependencies=[Depends(public_rate_limiter)],
    responses={
        422: {"model": ProblemDetail, "description": "Validation error"},
        429: {"model": ProblemDetail, "description": "Rate limit exceeded"},
    },
)

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    summary="Register a new customer or merchant account",
    responses={409: {"model": ProblemDetail, "description": "Email already registered"}},
)
async def register(payload: RegisterRequest, db: DbSession) -> User:
    return await register_user(
        db,
        email=payload.email,
        password=payload.password,
        role=UserRole(payload.role),
    )


@router.post(
    "/login",
    response_model=UserResponse,
    summary="Authenticate and receive auth cookies",
    responses={401: {"model": ProblemDetail, "description": "Invalid credentials"}},
)
async def login(payload: LoginRequest, response: Response, db: DbSession) -> User:
    user = await authenticate_user(db, email=payload.email, password=payload.password)

    family_id = uuid.uuid4().hex
    refresh_token, jti = create_refresh_token(user.id, family_id)
    await token_store.start_family(family_id, jti)

    access_token = create_access_token(user.id, user.role.value)
    set_auth_cookies(response, access_token, refresh_token)
    return user


@router.post(
    "/refresh",
    response_model=UserResponse,
    summary="Rotate the refresh token and refresh the access token",
    responses={401: {"model": ProblemDetail, "description": "Invalid or reused token"}},
)
async def refresh(
    response: Response,
    db: DbSession,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> User:
    if not refresh_token:
        raise _refresh_unauthorized("Missing refresh token.")

    try:
        claims = decode_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
        user_id = uuid.UUID(claims["sub"])
        family_id = claims["fid"]
        old_jti = claims["jti"]
    except (TokenError, KeyError, ValueError) as exc:
        raise _refresh_unauthorized("Invalid refresh token.") from exc

    # Load the user before rotating so a deleted/disabled account can't refresh.
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        await token_store.revoke_family(family_id)
        clear_auth_cookies(response)
        raise _refresh_unauthorized("User no longer exists.")

    new_refresh_token, new_jti = create_refresh_token(user.id, family_id)
    rotated = await token_store.rotate(family_id, old_jti, new_jti)
    if not rotated:
        # Reuse of a consumed token — the family has been burned. Force re-login.
        clear_auth_cookies(response)
        raise _refresh_unauthorized("Refresh token has been revoked.")

    new_access_token = create_access_token(user.id, user.role.value)
    set_auth_cookies(response, new_access_token, new_refresh_token)
    return user


@router.delete(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the refresh token family and clear auth cookies",
)
async def logout(
    response: Response,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> Response:
    if refresh_token:
        try:
            claims = decode_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
            await token_store.revoke_family(claims["fid"])
        except TokenError, KeyError:
            # Already-invalid token: nothing to revoke, still clear cookies.
            pass

    clear_auth_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


def _refresh_unauthorized(detail: str) -> ProblemException:
    return ProblemException(status_code=401, detail=detail, title="Unauthorized")
