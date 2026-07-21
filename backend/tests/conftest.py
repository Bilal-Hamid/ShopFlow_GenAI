"""Shared test fixtures.

Test env vars are set *before* any ``app`` import so the module-level Settings,
DB engine, and Redis client all bind to the test services. Defaults target the
dedicated test containers (Postgres on 5433, Redis on 6380); override via the
same env vars to point elsewhere (e.g. in CI).
"""

import os

os.environ.setdefault("APP_ENV", "local")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5433/shopflow_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-0123456789-abcdef")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_secret_0123456789abcdef")
# Cookies must be sendable over the http test transport.
os.environ.setdefault("COOKIE_SECURE", "false")

from collections.abc import AsyncGenerator  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.redis import redis_client  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import *  # noqa: E402,F403  (register all tables on Base.metadata)


@pytest.fixture(scope="session", autouse=True)
async def _create_schema() -> AsyncGenerator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    await redis_client.aclose()


@pytest.fixture(autouse=True)
async def _clean_state() -> AsyncGenerator[None]:
    """Reset DB rows and Redis between tests for isolation."""
    await redis_client.flushdb()
    yield
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    await redis_client.flushdb()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
