"""Server-side refresh-token tracking in Redis (rotation + reuse detection).

Rotation strategy
-----------------
Each login starts a token *family* identified by ``fid``. A family is a Redis
set holding the ``jti`` of every refresh token currently valid within it:

    refresh_family:{fid} -> { jti, ... }   (TTL = refresh token lifetime)

- **Login**: create a fresh family with the first jti.
- **Refresh**: atomically remove the presented jti from its family.
    * removed  -> it was valid: add the new jti and re-arm the TTL (rotation).
    * missing  -> the token was already rotated away or never existed: this is a
      replay of a consumed refresh token. Delete the whole family so every
      outstanding token in it is invalidated and the user must re-authenticate.
- **Logout**: delete the family.

``SREM`` returning whether the member existed makes the valid-vs-reuse decision
a single atomic operation, so concurrent refreshes can't both succeed.
"""

from app.core.config import settings
from app.db.redis import redis_client

_FAMILY_TTL_SECONDS = settings.refresh_token_expire_days * 24 * 60 * 60


def _family_key(family_id: str) -> str:
    return f"refresh_family:{family_id}"


async def start_family(family_id: str, jti: str) -> None:
    """Begin a new refresh-token family (called on login)."""
    key = _family_key(family_id)
    await redis_client.sadd(key, jti)
    await redis_client.expire(key, _FAMILY_TTL_SECONDS)


async def rotate(family_id: str, old_jti: str, new_jti: str) -> bool:
    """Consume ``old_jti`` and issue ``new_jti`` within the family.

    Returns True on a valid rotation. Returns False if ``old_jti`` was not a
    live member (reuse/invalid), in which case the entire family is revoked.
    """
    key = _family_key(family_id)
    removed = await redis_client.srem(key, old_jti)
    if removed == 1:
        await redis_client.sadd(key, new_jti)
        await redis_client.expire(key, _FAMILY_TTL_SECONDS)
        return True

    # Reuse of a consumed/unknown token — burn the whole family.
    await redis_client.delete(key)
    return False


async def revoke_family(family_id: str) -> None:
    """Invalidate every token in a family (called on logout)."""
    await redis_client.delete(_family_key(family_id))
