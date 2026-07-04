"""Auth business logic: user creation and credential verification.

Kept separate from the route layer so the rules (duplicate-email handling,
constant-time credential checks) are unit-testable without HTTP.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ProblemException
from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole

# A precomputed Argon2 hash used to equalise timing when the email is unknown,
# so login latency doesn't leak whether an account exists.
_DUMMY_HASH = hash_password("timing-equalisation-placeholder-000")


async def register_user(db: AsyncSession, *, email: str, password: str, role: UserRole) -> User:
    normalized_email = email.strip().lower()

    # The email column is globally unique (including soft-deleted rows), so any
    # existing row is a conflict.
    existing = await db.scalar(select(User.id).where(User.email == normalized_email))
    if existing is not None:
        raise ProblemException(
            status_code=409,
            detail="An account with this email already exists.",
            title="Conflict",
        )

    user = User(
        email=normalized_email,
        password_hash=hash_password(password),
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, *, email: str, password: str) -> User:
    normalized_email = email.strip().lower()
    user = await db.scalar(
        select(User).where(User.email == normalized_email, User.deleted_at.is_(None))
    )

    if user is None:
        # Verify against a dummy hash so timing is comparable to the found path.
        verify_password(password, _DUMMY_HASH)
        raise _invalid_credentials()

    if not verify_password(password, user.password_hash):
        raise _invalid_credentials()

    return user


def _invalid_credentials() -> ProblemException:
    return ProblemException(
        status_code=401,
        detail="Incorrect email or password.",
        title="Unauthorized",
    )
