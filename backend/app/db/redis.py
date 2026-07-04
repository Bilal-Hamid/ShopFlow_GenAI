from redis.asyncio import Redis

from app.core.config import settings

# One module-level async Redis client, mirroring the module-level engine in
# session.py. from_url manages an internal connection pool. decode_responses=True
# so reads come back as str (jti values, rate-limit counters) not bytes.
redis_client: Redis = Redis.from_url(settings.redis_url, decode_responses=True)
