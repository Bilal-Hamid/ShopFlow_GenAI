"""Integration tests for the Orders endpoint group."""

import uuid

from httpx import AsyncClient

from app.db.session import AsyncSessionLocal
from app.models.coupon import DiscountType
from app.models.product import Product
from app.models.user import UserRole
from tests.helpers import logged_in_client, make_coupon, make_product, make_user

_ADDRESS = {
    "full_name": "Ada Lovelace",
    "line1": "1 Analytical Way",
    "city": "London",
    "postal_code": "EC1A",
    "country": "UK",
}


async def _add_to_cart(cc: AsyncClient, product_id: uuid.UUID, quantity: int) -> None:
    resp = await cc.post("/cart/items", json={"product_id": str(product_id), "quantity": quantity})
    assert resp.status_code == 201, resp.text


async def _checkout(cc: AsyncClient, **extra):
    return await cc.post("/orders/checkout", json={"shipping_address": _ADDRESS, **extra})


async def test_checkout_creates_order_and_decrements_stock(client: AsyncClient):
    await make_user("c@shop.com", UserRole.CUSTOMER)
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=merchant.id, price="10.00", stock_qty=5)

    async with logged_in_client("c@shop.com") as cc:
        await _add_to_cart(cc, product.id, 2)
        resp = await _checkout(cc)
        assert resp.status_code == 201, resp.text
        order = resp.json()
        assert order["status"] == "pending"
        assert order["total_amount"] == "20.00"
        assert order["items"][0]["unit_price"] == "10.00"

        # Cart is emptied after checkout.
        assert (await cc.get("/cart")).json()["item_count"] == 0

    async with AsyncSessionLocal() as session:
        refreshed = await session.get(Product, product.id)
        assert refreshed.stock_qty == 3


async def test_checkout_empty_cart_is_422(client: AsyncClient):
    await make_user("c@shop.com", UserRole.CUSTOMER)
    async with logged_in_client("c@shop.com") as cc:
        resp = await _checkout(cc)
    assert resp.status_code == 422


async def test_price_snapshot_survives_later_price_change(client: AsyncClient):
    await make_user("c@shop.com", UserRole.CUSTOMER)
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=merchant.id, price="10.00", stock_qty=5)

    async with logged_in_client("c@shop.com") as cc:
        await _add_to_cart(cc, product.id, 1)
        order = (await _checkout(cc)).json()
        order_id = order["id"]

        async with AsyncSessionLocal() as session:
            db_product = await session.get(Product, product.id)
            db_product.price = 99
            await session.commit()

        fetched = await cc.get(f"/orders/{order_id}")
    assert fetched.json()["items"][0]["unit_price"] == "10.00"


async def test_checkout_with_percent_coupon(client: AsyncClient):
    await make_user("c@shop.com", UserRole.CUSTOMER)
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=merchant.id, price="100.00", stock_qty=5)
    await make_coupon(code="HALF", discount_type=DiscountType.PERCENT, value="50")

    async with logged_in_client("c@shop.com") as cc:
        await _add_to_cart(cc, product.id, 1)
        resp = await _checkout(cc, coupon_code="HALF")
    assert resp.status_code == 201
    assert resp.json()["total_amount"] == "50.00"


async def test_checkout_with_flat_coupon(client: AsyncClient):
    await make_user("c@shop.com", UserRole.CUSTOMER)
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=merchant.id, price="30.00", stock_qty=5)
    await make_coupon(code="TEN", discount_type=DiscountType.FLAT, value="10")

    async with logged_in_client("c@shop.com") as cc:
        await _add_to_cart(cc, product.id, 1)
        resp = await _checkout(cc, coupon_code="TEN")
    assert resp.json()["total_amount"] == "20.00"


async def test_invalid_coupon_is_422(client: AsyncClient):
    await make_user("c@shop.com", UserRole.CUSTOMER)
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=merchant.id, stock_qty=5)

    async with logged_in_client("c@shop.com") as cc:
        await _add_to_cart(cc, product.id, 1)
        resp = await _checkout(cc, coupon_code="NOPE")
    assert resp.status_code == 422


async def test_coupon_usage_limit_enforced(client: AsyncClient):
    await make_user("c@shop.com", UserRole.CUSTOMER)
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=merchant.id, price="10.00", stock_qty=10)
    await make_coupon(code="ONCE", discount_type=DiscountType.FLAT, value="1", usage_limit=1)

    async with logged_in_client("c@shop.com") as cc:
        await _add_to_cart(cc, product.id, 1)
        first = await _checkout(cc, coupon_code="ONCE")
        assert first.status_code == 201

        await _add_to_cart(cc, product.id, 1)
        second = await _checkout(cc, coupon_code="ONCE")
    assert second.status_code == 409


async def test_order_visibility_isolation(client: AsyncClient):
    await make_user("c1@shop.com", UserRole.CUSTOMER)
    await make_user("c2@shop.com", UserRole.CUSTOMER)
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=merchant.id, stock_qty=10)

    async with logged_in_client("c1@shop.com") as c1:
        await _add_to_cart(c1, product.id, 1)
        order_id = (await _checkout(c1)).json()["id"]

    # Another customer cannot see it.
    async with logged_in_client("c2@shop.com") as c2:
        assert (await c2.get(f"/orders/{order_id}")).status_code == 404
        assert (await c2.get("/orders")).json()["items"] == []

    # The merchant whose product is in the order can see it.
    async with logged_in_client("m@shop.com") as mc:
        listing = await mc.get("/orders")
        assert {o["id"] for o in listing.json()["items"]} == {order_id}


async def test_merchant_advances_status_customer_cancels(client: AsyncClient):
    await make_user("c@shop.com", UserRole.CUSTOMER)
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=merchant.id, stock_qty=10)

    async with logged_in_client("c@shop.com") as cc:
        await _add_to_cart(cc, product.id, 2)
        order_id = (await _checkout(cc)).json()["id"]

        # Customer cannot advance to shipped.
        bad = await cc.patch(f"/orders/{order_id}/status", json={"status": "shipped"})
        assert bad.status_code == 403

    async with logged_in_client("m@shop.com") as mc:
        # Merchant advances forward.
        ok = await mc.patch(f"/orders/{order_id}/status", json={"status": "confirmed"})
        assert ok.status_code == 200
        assert ok.json()["status"] == "confirmed"

        # Merchant cannot move backward.
        back = await mc.patch(f"/orders/{order_id}/status", json={"status": "pending"})
        assert back.status_code == 409

        # Merchant cannot cancel.
        cancel = await mc.patch(f"/orders/{order_id}/status", json={"status": "cancelled"})
        assert cancel.status_code == 403

    async with logged_in_client("c@shop.com") as cc:
        cancelled = await cc.patch(f"/orders/{order_id}/status", json={"status": "cancelled"})
        assert cancelled.status_code == 200

    # Cancelling restocked the product (10 - 2, then +2 back = 10).
    async with AsyncSessionLocal() as session:
        refreshed = await session.get(Product, product.id)
        assert refreshed.stock_qty == 10


async def test_tracking_shape(client: AsyncClient):
    await make_user("c@shop.com", UserRole.CUSTOMER)
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=merchant.id, stock_qty=10)

    async with logged_in_client("c@shop.com") as cc:
        await _add_to_cart(cc, product.id, 1)
        order_id = (await _checkout(cc)).json()["id"]
        resp = await cc.get(f"/orders/{order_id}/tracking")

    body = resp.json()
    assert resp.status_code == 200
    assert body["status"] == "pending"
    assert body["carrier"] == "ShopFlow Logistics"
    assert body["timeline"][0]["status"] == "pending"
    assert body["timeline"][0]["reached"] is True
    assert body["timeline"][-1]["reached"] is False


async def test_tracking_for_cancelled_order(client: AsyncClient):
    await make_user("c@shop.com", UserRole.CUSTOMER)
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=merchant.id, stock_qty=10)

    async with logged_in_client("c@shop.com") as cc:
        await _add_to_cart(cc, product.id, 1)
        order_id = (await _checkout(cc)).json()["id"]
        await cc.patch(f"/orders/{order_id}/status", json={"status": "cancelled"})
        resp = await cc.get(f"/orders/{order_id}/tracking")

    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["carrier"] is None
    assert body["estimated_delivery"] is None
    assert body["timeline"][-1]["status"] == "cancelled"


async def test_orders_list_pagination(client: AsyncClient):
    await make_user("c@shop.com", UserRole.CUSTOMER)
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=merchant.id, stock_qty=10)

    async with logged_in_client("c@shop.com") as cc:
        for _ in range(3):
            await _add_to_cart(cc, product.id, 1)
            assert (await _checkout(cc)).status_code == 201

        first = await cc.get("/orders", params={"limit": 2})
        body = first.json()
        assert len(body["items"]) == 2
        assert body["nextCursor"] is not None

        second = await cc.get("/orders", params={"limit": 2, "cursor": body["nextCursor"]})
        body2 = second.json()
    assert len(body2["items"]) == 1
    ids1 = {o["id"] for o in body["items"]}
    ids2 = {o["id"] for o in body2["items"]}
    assert ids1.isdisjoint(ids2)


async def test_checkout_requires_customer(client: AsyncClient):
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    await make_product(merchant_id=merchant.id, stock_qty=5)
    async with logged_in_client("m@shop.com") as mc:
        resp = await _checkout(mc)
    assert resp.status_code == 403


async def test_admin_sees_all_orders(client: AsyncClient):
    await make_user("c@shop.com", UserRole.CUSTOMER)
    await make_user("admin@shop.com", UserRole.ADMIN)
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=merchant.id, stock_qty=10)

    async with logged_in_client("c@shop.com") as cc:
        await _add_to_cart(cc, product.id, 1)
        await _checkout(cc)

    async with logged_in_client("admin@shop.com") as admin:
        listing = await admin.get("/orders")
    assert len(listing.json()["items"]) == 1
