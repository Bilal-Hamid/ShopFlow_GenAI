"""Password hashing (Argon2) and JWT creation/verification.

Token model
-----------
Two token types, both signed JWTs, distinguished by a ``type`` claim:

- ``access``  (15 min)  — carries ``sub`` (user id) and ``role``; sent on every
  request via the ``access_token`` cookie.
- ``refresh`` (7 days)  — carries ``sub`` and ``fid`` (a per-login *family* id);
  sent only to ``/auth`` routes via the ``refresh_token`` cookie.

Refresh tokens are additionally tracked server-side in Redis (see
``app/services/token_store.py``) so they can be rotated on use, revoked on
logout, and detected on reuse. The ``jti`` claim is the per-token id recorded
there.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings

_password_hasher = PasswordHasher()

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


class TokenError(Exception):
    """Raised when a JWT is missing, malformed, expired, or the wrong type."""


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        # Malformed/legacy hash — treat as a failed verification, never crash.
        return False


def _encode(claims: dict[str, Any], expires_delta: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {
        **claims,
        "iat": now,
        "exp": now + expires_delta,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    return _encode(
        {"sub": str(user_id), "role": role, "type": ACCESS_TOKEN_TYPE},
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: uuid.UUID, family_id: str) -> tuple[str, str]:
    """Return ``(token, jti)``. The jti is what gets stored in the token family."""
    now = datetime.now(UTC)
    jti = uuid.uuid4().hex
    payload = {
        "sub": str(user_id),
        "fid": family_id,
        "type": REFRESH_TOKEN_TYPE,
        "iat": now,
        "exp": now + timedelta(days=settings.refresh_token_expire_days),
        "jti": jti,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti


def decode_token(token: str, *, expected_type: str) -> dict[str, Any]:
    """Decode and validate a JWT, enforcing signature, expiry, and token type."""
    try:
        claims = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc

    if claims.get("type") != expected_type:
        raise TokenError(f"expected {expected_type} token")
    return claims
