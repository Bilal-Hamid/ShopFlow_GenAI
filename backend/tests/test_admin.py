"""Integration tests for the Admin endpoint group."""

from httpx import AsyncClient

from app.models.order import OrderStatus
from app.models.user import UserRole
from tests.helpers import (
    DEFAULT_PASSWORD,
    logged_in_client,
    make_order,
    make_product,
    make_user,
)


async def test_admin_endpoints_require_admin_role(client: AsyncClient):
    await make_user("m@shop.com", UserRole.MERCHANT)
    async with logged_in_client("m@shop.com") as mc:
        for path in ("/admin/users", "/admin/orders", "/admin/platform-stats"):
            assert (await mc.get(path)).status_code == 403


async def test_list_users_role_filter_and_include_deleted(client: AsyncClient):
    await make_user("admin@shop.com", UserRole.ADMIN)
    await make_user("m@shop.com", UserRole.MERCHANT)
    deleted = await make_user("gone@shop.com", UserRole.CUSTOMER)

    async with logged_in_client("admin@shop.com") as admin:
        # Deactivate one customer, then confirm default listing hides it.
        await admin.patch(f"/admin/users/{deleted.id}", json={"is_active": False})

        default = (await admin.get("/admin/users")).json()
        emails = {u["email"] for u in default["items"]}
        assert "gone@shop.com" not in emails
        assert {"admin@shop.com", "m@shop.com"} <= emails

        with_deleted = (await admin.get("/admin/users", params={"include_deleted": True})).json()
        assert any(u["email"] == "gone@shop.com" for u in with_deleted["items"])

        merchants = (await admin.get("/admin/users", params={"role": "merchant"})).json()
        assert [u["email"] for u in merchants["items"]] == ["m@shop.com"]


async def test_update_user_never_leaks_password_hash(client: AsyncClient):
    await make_user("admin@shop.com", UserRole.ADMIN)
    target = await make_user("u@shop.com", UserRole.CUSTOMER)
    async with logged_in_client("admin@shop.com") as admin:
        resp = await admin.patch(f"/admin/users/{target.id}", json={"role": "merchant"})
    body = resp.json()
    assert resp.status_code == 200
    assert body["role"] == "merchant"
    assert "password_hash" not in body


async def test_empty_patch_is_422(client: AsyncClient):
    await make_user("admin@shop.com", UserRole.ADMIN)
    target = await make_user("u@shop.com", UserRole.CUSTOMER)
    async with logged_in_client("admin@shop.com") as admin:
        resp = await admin.patch(f"/admin/users/{target.id}", json={})
    assert resp.status_code == 422


async def test_recovery_flow_resets_email_and_password(client: AsyncClient):
    await make_user("admin@shop.com", UserRole.ADMIN)
    await make_user("old@shop.com", UserRole.CUSTOMER)

    async with logged_in_client("admin@shop.com") as admin:
        target_id = await _find_user_id(admin, "old@shop.com")
        resp = await admin.patch(
            f"/admin/users/{target_id}",
            json={"email": "new@shop.com", "password": "newpass99"},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "new@shop.com"

    # Old credentials no longer work; new ones do.
    bad = await client.post(
        "/auth/login", json={"email": "old@shop.com", "password": DEFAULT_PASSWORD}
    )
    assert bad.status_code == 401
    good = await client.post("/auth/login", json={"email": "new@shop.com", "password": "newpass99"})
    assert good.status_code == 200


async def test_email_collision_is_409(client: AsyncClient):
    await make_user("admin@shop.com", UserRole.ADMIN)
    await make_user("taken@shop.com", UserRole.CUSTOMER)
    target = await make_user("u@shop.com", UserRole.CUSTOMER)

    async with logged_in_client("admin@shop.com") as admin:
        resp = await admin.patch(f"/admin/users/{target.id}", json={"email": "taken@shop.com"})
    assert resp.status_code == 409


async def test_weak_password_rejected_422(client: AsyncClient):
    await make_user("admin@shop.com", UserRole.ADMIN)
    target = await make_user("u@shop.com", UserRole.CUSTOMER)
    async with logged_in_client("admin@shop.com") as admin:
        resp = await admin.patch(f"/admin/users/{target.id}", json={"password": "short"})
    assert resp.status_code == 422


async def test_deactivate_then_reactivate_toggles_login(client: AsyncClient):
    await make_user("admin@shop.com", UserRole.ADMIN)
    target = await make_user("u@shop.com", UserRole.CUSTOMER)

    async with logged_in_client("admin@shop.com") as admin:
        await admin.patch(f"/admin/users/{target.id}", json={"is_active": False})

    disabled = await client.post(
        "/auth/login", json={"email": "u@shop.com", "password": DEFAULT_PASSWORD}
    )
    assert disabled.status_code == 401

    async with logged_in_client("admin@shop.com") as admin:
        await admin.patch(f"/admin/users/{target.id}", json={"is_active": True})

    restored = await client.post(
        "/auth/login", json={"email": "u@shop.com", "password": DEFAULT_PASSWORD}
    )
    assert restored.status_code == 200


async def test_admin_cannot_demote_self(client: AsyncClient):
    admin_user = await make_user("admin@shop.com", UserRole.ADMIN)
    await make_user("admin2@shop.com", UserRole.ADMIN)  # not the last admin
    async with logged_in_client("admin@shop.com") as admin:
        resp = await admin.patch(f"/admin/users/{admin_user.id}", json={"role": "customer"})
    assert resp.status_code == 403


async def test_last_admin_is_protected(client: AsyncClient):
    only_admin = await make_user("admin@shop.com", UserRole.ADMIN)
    other_admin = await make_user("admin2@shop.com", UserRole.ADMIN)

    async with logged_in_client("admin@shop.com") as admin:
        # With two admins, demoting the *other* one succeeds.
        ok = await admin.patch(f"/admin/users/{other_admin.id}", json={"role": "merchant"})
        assert ok.status_code == 200
        # admin@ is now the sole admin and cannot strip their own rights, which
        # is what guarantees the platform always keeps at least one admin.
        blocked = await admin.patch(f"/admin/users/{only_admin.id}", json={"role": "customer"})
    assert blocked.status_code == 403


async def test_update_missing_user_is_404(client: AsyncClient):
    await make_user("admin@shop.com", UserRole.ADMIN)
    async with logged_in_client("admin@shop.com") as admin:
        resp = await admin.patch(
            "/admin/users/00000000-0000-0000-0000-000000000000", json={"role": "merchant"}
        )
    assert resp.status_code == 404


async def test_admin_orders_sees_all_and_filters(client: AsyncClient):
    customer = await make_user("c@shop.com", UserRole.CUSTOMER)
    await make_user("admin@shop.com", UserRole.ADMIN)
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=merchant.id, stock_qty=100)
    await make_order(customer_id=customer.id, lines=[(product, 1)], status=OrderStatus.DELIVERED)
    await make_order(customer_id=customer.id, lines=[(product, 1)], status=OrderStatus.PENDING)

    async with logged_in_client("admin@shop.com") as admin:
        assert len((await admin.get("/admin/orders")).json()["items"]) == 2
        delivered = (await admin.get("/admin/orders", params={"status": "delivered"})).json()
    assert len(delivered["items"]) == 1


async def test_users_list_pagination(client: AsyncClient):
    await make_user("admin@shop.com", UserRole.ADMIN)
    for i in range(4):
        await make_user(f"u{i}@shop.com", UserRole.CUSTOMER)

    async with logged_in_client("admin@shop.com") as admin:
        first = (await admin.get("/admin/users", params={"limit": 2})).json()
        assert len(first["items"]) == 2
        assert first["nextCursor"] is not None

        second = (
            await admin.get("/admin/users", params={"limit": 2, "cursor": first["nextCursor"]})
        ).json()
        assert len(second["items"]) == 2

        ids1 = {u["id"] for u in first["items"]}
        ids2 = {u["id"] for u in second["items"]}
    assert ids1.isdisjoint(ids2)


async def test_users_list_rejects_bad_cursor(client: AsyncClient):
    await make_user("admin@shop.com", UserRole.ADMIN)
    async with logged_in_client("admin@shop.com") as admin:
        resp = await admin.get("/admin/users", params={"cursor": "!!!not-base64!!!"})
    assert resp.status_code == 422


async def test_platform_stats_shape(client: AsyncClient):
    customer = await make_user("c@shop.com", UserRole.CUSTOMER)
    await make_user("admin@shop.com", UserRole.ADMIN)
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=merchant.id, price="10.00", stock_qty=100)
    await make_order(customer_id=customer.id, lines=[(product, 2)], status=OrderStatus.DELIVERED)

    async with logged_in_client("admin@shop.com") as admin:
        body = (await admin.get("/admin/platform-stats")).json()

    assert body["total_users"] == 3
    assert body["users_by_role"]["admin"] == 1
    assert body["users_by_role"]["merchant"] == 1
    assert body["total_products"] == 1
    assert body["products_by_status"]["active"] == 1
    assert body["total_orders"] == 1
    assert body["orders_by_status"]["delivered"] == 1
    assert body["total_revenue"] == "20.00"
    assert body["revenue"]["all_time"] == "20.00"


async def _find_user_id(admin: AsyncClient, email: str) -> str:
    resp = await admin.get("/admin/users", params={"include_deleted": True, "limit": 100})
    return next(u["id"] for u in resp.json()["items"] if u["email"] == email)
