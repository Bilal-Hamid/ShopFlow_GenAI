"""End-to-end auth flow over HTTP against real Postgres + Redis."""

from httpx import ASGITransport, AsyncClient

from app.api.cookies import ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME
from app.main import app

PROBLEM_JSON = "application/problem+json"


async def _register(
    client: AsyncClient, email="user@shop.com", password="abcd1234", role="customer"
):
    return await client.post(
        "/auth/register", json={"email": email, "password": password, "role": role}
    )


# --- register --------------------------------------------------------------


async def test_register_success(client: AsyncClient):
    resp = await _register(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "user@shop.com"
    assert body["role"] == "customer"
    assert "id" in body and "created_at" in body
    assert "password_hash" not in body and "password" not in body
    # Register does not issue cookies; login does.
    assert ACCESS_COOKIE_NAME not in resp.cookies
    assert REFRESH_COOKIE_NAME not in resp.cookies


async def test_register_normalizes_email(client: AsyncClient):
    resp = await _register(client, email="MixedCase@Shop.com")
    assert resp.status_code == 201
    assert resp.json()["email"] == "mixedcase@shop.com"


async def test_register_duplicate_conflicts(client: AsyncClient):
    await _register(client)
    resp = await _register(client)
    assert resp.status_code == 409
    assert resp.headers["content-type"].startswith(PROBLEM_JSON)
    assert resp.json()["status"] == 409


async def test_register_admin_role_rejected(client: AsyncClient):
    resp = await _register(client, role="admin")
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith(PROBLEM_JSON)


async def test_register_validation_error_is_problem_json(client: AsyncClient):
    resp = await client.post("/auth/register", json={"email": "bad", "password": "x"})
    assert resp.status_code == 422
    body = resp.json()
    assert resp.headers["content-type"].startswith(PROBLEM_JSON)
    assert set(body) >= {"type", "title", "status", "detail", "instance"}
    assert body["instance"] == "/auth/register"


# --- login -----------------------------------------------------------------


async def test_login_success_sets_httponly_cookies(client: AsyncClient):
    await _register(client)
    resp = await client.post("/auth/login", json={"email": "user@shop.com", "password": "abcd1234"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "user@shop.com"

    set_cookies = "; ".join(resp.headers.get_list("set-cookie"))
    assert ACCESS_COOKIE_NAME in set_cookies
    assert REFRESH_COOKIE_NAME in set_cookies
    assert "HttpOnly" in set_cookies


async def test_login_wrong_password(client: AsyncClient):
    await _register(client)
    resp = await client.post(
        "/auth/login", json={"email": "user@shop.com", "password": "wrongpass1"}
    )
    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith(PROBLEM_JSON)


async def test_login_unknown_email(client: AsyncClient):
    resp = await client.post(
        "/auth/login", json={"email": "ghost@shop.com", "password": "abcd1234"}
    )
    assert resp.status_code == 401


# --- refresh / rotation ----------------------------------------------------


async def test_refresh_rotates_refresh_token(client: AsyncClient):
    await _register(client)
    await client.post("/auth/login", json={"email": "user@shop.com", "password": "abcd1234"})
    old_refresh = client.cookies.get(REFRESH_COOKIE_NAME)

    resp = await client.post("/auth/refresh")
    assert resp.status_code == 200
    new_refresh = client.cookies.get(REFRESH_COOKIE_NAME)
    assert new_refresh is not None
    assert new_refresh != old_refresh


async def test_refresh_reuse_is_detected(client: AsyncClient):
    await _register(client)
    await client.post("/auth/login", json={"email": "user@shop.com", "password": "abcd1234"})
    old_refresh = client.cookies.get(REFRESH_COOKIE_NAME)

    # Valid rotation once.
    await client.post("/auth/refresh")

    # Replay the original (now consumed) refresh token via a clean client.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as attacker:
        attacker.cookies.set(REFRESH_COOKIE_NAME, old_refresh, path="/auth")
        resp = await attacker.post("/auth/refresh")
    assert resp.status_code == 401


async def test_refresh_without_cookie(client: AsyncClient):
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 401


# --- logout ----------------------------------------------------------------


async def test_logout_clears_cookies_and_revokes(client: AsyncClient):
    await _register(client)
    await client.post("/auth/login", json={"email": "user@shop.com", "password": "abcd1234"})

    resp = await client.delete("/auth/logout")
    assert resp.status_code == 204

    # Refresh token family revoked -> further refresh fails.
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 401


async def test_full_lifecycle(client: AsyncClient):
    assert (await _register(client, role="merchant")).status_code == 201
    assert (
        await client.post("/auth/login", json={"email": "user@shop.com", "password": "abcd1234"})
    ).status_code == 200
    assert (await client.post("/auth/refresh")).status_code == 200
    assert (await client.delete("/auth/logout")).status_code == 204
