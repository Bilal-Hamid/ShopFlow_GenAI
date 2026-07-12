"""Integration tests for the Cart endpoint group (Redis-backed)."""

import uuid

from httpx import AsyncClient

from app.models.product import ProductStatus
from app.models.user import UserRole
from tests.helpers import logged_in_client, make_product, make_user


async def _setup_customer_and_product(**product_kwargs):
    customer = await make_user("c@shop.com", UserRole.CUSTOMER)
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=merchant.id, **product_kwargs)
    return customer, product


async def test_empty_cart(client: AsyncClient):
    await make_user("c@shop.com", UserRole.CUSTOMER)
    async with logged_in_client("c@shop.com") as cc:
        resp = await cc.get("/cart")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "item_count": 0, "subtotal": "0.00"}


async def test_add_item_and_totals(client: AsyncClient):
    _, product = await _setup_customer_and_product(price="10.00", stock_qty=5)
    async with logged_in_client("c@shop.com") as cc:
        resp = await cc.post("/cart/items", json={"product_id": str(product.id), "quantity": 2})
    assert resp.status_code == 201
    body = resp.json()
    assert body["item_count"] == 2
    assert body["subtotal"] == "20.00"
    assert body["items"][0]["line_total"] == "20.00"


async def test_add_item_accumulates_quantity(client: AsyncClient):
    _, product = await _setup_customer_and_product(stock_qty=10)
    async with logged_in_client("c@shop.com") as cc:
        await cc.post("/cart/items", json={"product_id": str(product.id), "quantity": 2})
        resp = await cc.post("/cart/items", json={"product_id": str(product.id), "quantity": 3})
    assert resp.json()["item_count"] == 5


async def test_add_exceeding_stock_is_409(client: AsyncClient):
    _, product = await _setup_customer_and_product(stock_qty=1)
    async with logged_in_client("c@shop.com") as cc:
        resp = await cc.post("/cart/items", json={"product_id": str(product.id), "quantity": 2})
    assert resp.status_code == 409


async def test_add_unknown_product_is_404(client: AsyncClient):
    await make_user("c@shop.com", UserRole.CUSTOMER)
    async with logged_in_client("c@shop.com") as cc:
        resp = await cc.post("/cart/items", json={"product_id": str(uuid.uuid4()), "quantity": 1})
    assert resp.status_code == 404


async def test_non_customer_cannot_use_cart(client: AsyncClient):
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=merchant.id)
    async with logged_in_client("m@shop.com") as mc:
        resp = await mc.post("/cart/items", json={"product_id": str(product.id), "quantity": 1})
    assert resp.status_code == 403


async def test_update_item_quantity(client: AsyncClient):
    _, product = await _setup_customer_and_product(stock_qty=10)
    async with logged_in_client("c@shop.com") as cc:
        await cc.post("/cart/items", json={"product_id": str(product.id), "quantity": 1})
        resp = await cc.patch(f"/cart/items/{product.id}", json={"quantity": 4})
    assert resp.status_code == 200
    assert resp.json()["item_count"] == 4


async def test_update_missing_item_is_404(client: AsyncClient):
    _, product = await _setup_customer_and_product()
    async with logged_in_client("c@shop.com") as cc:
        resp = await cc.patch(f"/cart/items/{product.id}", json={"quantity": 1})
    assert resp.status_code == 404


async def test_remove_item(client: AsyncClient):
    _, product = await _setup_customer_and_product(stock_qty=10)
    async with logged_in_client("c@shop.com") as cc:
        await cc.post("/cart/items", json={"product_id": str(product.id), "quantity": 1})
        resp = await cc.delete(f"/cart/items/{product.id}")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


async def test_remove_missing_item_is_404(client: AsyncClient):
    _, product = await _setup_customer_and_product()
    async with logged_in_client("c@shop.com") as cc:
        resp = await cc.delete(f"/cart/items/{product.id}")
    assert resp.status_code == 404


async def test_clear_cart(client: AsyncClient):
    _, product = await _setup_customer_and_product(stock_qty=10)
    async with logged_in_client("c@shop.com") as cc:
        await cc.post("/cart/items", json={"product_id": str(product.id), "quantity": 2})
        cleared = await cc.delete("/cart")
        assert cleared.status_code == 204
        after = await cc.get("/cart")
    assert after.json()["item_count"] == 0


async def test_cart_prunes_archived_product(client: AsyncClient):
    from app.db.session import AsyncSessionLocal
    from app.models.product import Product

    _, product = await _setup_customer_and_product(stock_qty=10)
    async with logged_in_client("c@shop.com") as cc:
        await cc.post("/cart/items", json={"product_id": str(product.id), "quantity": 1})

        # Archive the product out from under the cart.
        async with AsyncSessionLocal() as session:
            db_product = await session.get(Product, product.id)
            db_product.status = ProductStatus.ARCHIVED
            await session.commit()

        resp = await cc.get("/cart")
    assert resp.json()["items"] == []
