"""Coupon validation and discount logic, used at checkout.

Coupons are validated server-side (never trust the client). ``usage_limit`` is
enforced with a Redis counter (``coupon_usage:{code}``) rather than a schema
change — consistent with the project's no-migration direction for this task.

Known trade-off: because the counter lives only in Redis, a Redis flush resets
usage counts. For durable enforcement this would move to a DB column with a
row-level lock. The reservation uses INCR-then-check (rolling back with DECR on
overflow) so two concurrent checkouts can't both consume the last use.
"""

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ProblemException
from app.db.redis import redis_client
from app.models.coupon import Coupon, DiscountType

_CENTS = Decimal("0.01")


def _usage_key(code: str) -> str:
    return f"coupon_usage:{code}"


async def validate_coupon(db: AsyncSession, code: str) -> Coupon:
    """Load a coupon by code and check it has not expired. Raises on failure."""
    coupon = await db.scalar(select(Coupon).where(Coupon.code == code))
    if coupon is None:
        raise ProblemException(
            status_code=422, detail="Invalid coupon code.", title="Unprocessable Entity"
        )
    if coupon.expires_at is not None and coupon.expires_at < datetime.now(UTC):
        raise ProblemException(
            status_code=422, detail="This coupon has expired.", title="Unprocessable Entity"
        )
    return coupon


def compute_discount(coupon: Coupon, subtotal: Decimal) -> Decimal:
    """Discount amount for ``subtotal``, never exceeding it, rounded to cents."""
    if coupon.discount_type == DiscountType.PERCENT:
        raw = subtotal * coupon.value / Decimal(100)
    else:  # FLAT
        raw = coupon.value
    discount = min(raw, subtotal)
    return discount.quantize(_CENTS, rounding=ROUND_HALF_UP)


async def reserve_usage(coupon: Coupon) -> None:
    """Atomically claim one use, rolling back and raising if the limit is hit."""
    if coupon.usage_limit is None:
        return
    key = _usage_key(coupon.code)
    used = await redis_client.incr(key)
    if used > coupon.usage_limit:
        await redis_client.decr(key)
        raise ProblemException(
            status_code=409,
            detail="This coupon has reached its usage limit.",
            title="Conflict",
        )


async def release_usage(coupon: Coupon) -> None:
    """Return a previously reserved use (called if checkout fails after reserving)."""
    if coupon.usage_limit is None:
        return
    await redis_client.decr(_usage_key(coupon.code))
