"""RBAC dependency tests (get_current_user + require_roles).

Temporary protected routes are mounted on the app so the shared auth/RBAC
dependencies can be exercised before real protected endpoints exist.
"""

from fastapi import Depends
from httpx import AsyncClient

from app.api.deps import CurrentUser, require_roles
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.user import User, UserRole


@app.get("/_test/me")
async def _me(user: CurrentUser) -> dict[str, str]:
    return {"role": user.role.value}


@app.get("/_test/admin", dependencies=[Depends(require_roles(UserRole.ADMIN))])
async def _admin_only() -> dict[str, bool]:
    return {"ok": True}


async def _make_user(email: str, role: UserRole, password: str = "abcd1234") -> None:
    async with AsyncSessionLocal() as session:
        session.add(User(email=email, password_hash=hash_password(password), role=role))
        await session.commit()


async def _login(client: AsyncClient, email: str, password: str = "abcd1234") -> None:
    resp = await client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200


async def test_protected_route_requires_authentication(client: AsyncClient):
    resp = await client.get("/_test/me")
    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith("application/problem+json")


async def test_current_user_resolved_from_cookie(client: AsyncClient):
    await _make_user("cust@shop.com", UserRole.CUSTOMER)
    await _login(client, "cust@shop.com")
    resp = await client.get("/_test/me")
    assert resp.status_code == 200
    assert resp.json()["role"] == "customer"


async def test_require_roles_forbids_wrong_role(client: AsyncClient):
    await _make_user("cust@shop.com", UserRole.CUSTOMER)
    await _login(client, "cust@shop.com")
    resp = await client.get("/_test/admin")
    assert resp.status_code == 403
    assert resp.headers["content-type"].startswith("application/problem+json")


async def test_require_roles_allows_correct_role(client: AsyncClient):
    await _make_user("admin@shop.com", UserRole.ADMIN)
    await _login(client, "admin@shop.com")
    resp = await client.get("/_test/admin")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


async def test_invalid_token_rejected(client: AsyncClient):
    client.cookies.set("access_token", "garbage.token.value", path="/")
    resp = await client.get("/_test/me")
    assert resp.status_code == 401
