"""Integration tests for the Products endpoint group."""

import uuid

from httpx import AsyncClient

from app.models.product import ProductStatus
from app.models.user import UserRole
from tests.helpers import logged_in_client, make_category, make_product, make_user


async def test_list_only_shows_active_products(client: AsyncClient):
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    await make_product(merchant_id=merchant.id, title="Active", status=ProductStatus.ACTIVE)
    await make_product(merchant_id=merchant.id, title="Draft", status=ProductStatus.DRAFT)

    resp = await client.get("/products")
    assert resp.status_code == 200
    titles = [p["title"] for p in resp.json()["items"]]
    assert titles == ["Active"]


async def test_list_pagination_returns_next_cursor(client: AsyncClient):
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    for i in range(3):
        await make_product(merchant_id=merchant.id, title=f"P{i}")

    first = await client.get("/products", params={"limit": 2})
    body = first.json()
    assert len(body["items"]) == 2
    assert body["nextCursor"] is not None

    second = await client.get("/products", params={"limit": 2, "cursor": body["nextCursor"]})
    body2 = second.json()
    assert len(body2["items"]) == 1
    assert body2["nextCursor"] is None

    # No overlap between pages.
    ids_page1 = {p["id"] for p in body["items"]}
    ids_page2 = {p["id"] for p in body2["items"]}
    assert ids_page1.isdisjoint(ids_page2)


async def test_invalid_cursor_is_422(client: AsyncClient):
    resp = await client.get("/products", params={"cursor": "not-a-valid-cursor"})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")


async def test_get_product_detail_and_not_found(client: AsyncClient):
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=merchant.id, title="Findme")
    draft = await make_product(merchant_id=merchant.id, status=ProductStatus.DRAFT)

    ok = await client.get(f"/products/{product.id}")
    assert ok.status_code == 200
    assert ok.json()["title"] == "Findme"

    # Draft is not publicly visible.
    hidden = await client.get(f"/products/{draft.id}")
    assert hidden.status_code == 404

    missing = await client.get(f"/products/{uuid.uuid4()}")
    assert missing.status_code == 404


async def test_search_by_text_and_price(client: AsyncClient):
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    await make_product(merchant_id=merchant.id, title="Blue Mug", price="5.00")
    await make_product(merchant_id=merchant.id, title="Red Plate", price="50.00")

    by_text = await client.get("/products/search", params={"q": "mug"})
    assert [p["title"] for p in by_text.json()["items"]] == ["Blue Mug"]

    by_price = await client.get("/products/search", params={"max_price": "10"})
    assert [p["title"] for p in by_price.json()["items"]] == ["Blue Mug"]


async def test_merchant_can_create_product(client: AsyncClient):
    await make_user("m@shop.com", UserRole.MERCHANT)
    async with logged_in_client("m@shop.com") as merchant_client:
        resp = await merchant_client.post(
            "/products",
            json={"title": "New", "price": "12.50", "stock_qty": 3, "status": "active"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "New"
    assert body["status"] == "active"


async def test_customer_cannot_create_product(client: AsyncClient):
    await make_user("c@shop.com", UserRole.CUSTOMER)
    async with logged_in_client("c@shop.com") as customer_client:
        resp = await customer_client.post("/products", json={"title": "x", "price": "1.00"})
    assert resp.status_code == 403


async def test_create_with_unknown_category_is_422(client: AsyncClient):
    await make_user("m@shop.com", UserRole.MERCHANT)
    async with logged_in_client("m@shop.com") as merchant_client:
        resp = await merchant_client.post(
            "/products",
            json={"title": "x", "price": "1.00", "category_id": str(uuid.uuid4())},
        )
    assert resp.status_code == 422


async def test_create_with_valid_category(client: AsyncClient):
    await make_user("m@shop.com", UserRole.MERCHANT)
    category = await make_category()
    async with logged_in_client("m@shop.com") as merchant_client:
        resp = await merchant_client.post(
            "/products",
            json={"title": "x", "price": "1.00", "category_id": str(category.id)},
        )
    assert resp.status_code == 201
    assert resp.json()["category_id"] == str(category.id)


async def test_only_owner_or_admin_can_update(client: AsyncClient):
    owner = await make_user("owner@shop.com", UserRole.MERCHANT)
    await make_user("other@shop.com", UserRole.MERCHANT)
    await make_user("admin@shop.com", UserRole.ADMIN)
    product = await make_product(merchant_id=owner.id, title="Orig")

    async with logged_in_client("other@shop.com") as other:
        forbidden = await other.patch(f"/products/{product.id}", json={"title": "Hacked"})
    assert forbidden.status_code == 403

    async with logged_in_client("owner@shop.com") as owner_client:
        ok = await owner_client.patch(f"/products/{product.id}", json={"title": "Updated"})
    assert ok.status_code == 200
    assert ok.json()["title"] == "Updated"

    async with logged_in_client("admin@shop.com") as admin_client:
        admin_ok = await admin_client.patch(f"/products/{product.id}", json={"price": "99.99"})
    assert admin_ok.status_code == 200
    assert admin_ok.json()["price"] == "99.99"


async def test_soft_delete_hides_product(client: AsyncClient):
    owner = await make_user("owner@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=owner.id)

    async with logged_in_client("owner@shop.com") as owner_client:
        deleted = await owner_client.delete(f"/products/{product.id}")
    assert deleted.status_code == 204

    # Now invisible to the public read paths.
    assert (await client.get(f"/products/{product.id}")).status_code == 404
    assert (await client.get("/products")).json()["items"] == []
