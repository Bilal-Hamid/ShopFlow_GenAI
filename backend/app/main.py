from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.routes.auth import router as auth_router
from app.core.config import settings
from app.db.redis import redis_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    yield
    # Release the Redis connection pool on shutdown.
    await redis_client.aclose()


app = FastAPI(title="ShopFlow API", version="0.1.0", lifespan=lifespan)

register_exception_handlers(app)
app.include_router(auth_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}
