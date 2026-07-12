"""Integration tests for the Merchant endpoint group."""

from httpx import AsyncClient

from app.models.order import OrderStatus
from app.models.product import ProductStatus
from app.models.user import UserRole
from tests.helpers import logged_in_client, make_order, make_product, make_user


async def test_merchant_endpoints_require_merchant_role(client: AsyncClient):
    await make_user("c@shop.com", UserRole.CUSTOMER)
    async with logged_in_client("c@shop.com") as cc:
        for path in ("/merchant/dashboard", "/merchant/products", "/merchant/revenue-summary"):
            assert (await cc.get(path)).status_code == 403


async def test_merchant_products_lists_all_statuses(client: AsyncClient):
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    await make_product(merchant_id=merchant.id, title="Active", status=ProductStatus.ACTIVE)
    await make_product(merchant_id=merchant.id, title="Draft", status=ProductStatus.DRAFT)
    await make_product(merchant_id=merchant.id, title="Archived", status=ProductStatus.ARCHIVED)

    async with logged_in_client("m@shop.com") as mc:
        # Public catalog exposes only the active one...
        assert len((await mc.get("/products")).json()["items"]) == 1
        # ...but the merchant view exposes all three.
        body = (await mc.get("/merchant/products")).json()
        assert {p["status"] for p in body["items"]} == {"active", "draft", "archived"}
        # Status filter narrows it.
        drafts = (await mc.get("/merchant/products", params={"status": "draft"})).json()
        assert [p["title"] for p in drafts["items"]] == ["Draft"]


async def test_merchant_products_excludes_other_merchants(client: AsyncClient):
    m1 = await make_user("m1@shop.com", UserRole.MERCHANT)
    m2 = await make_user("m2@shop.com", UserRole.MERCHANT)
    await make_product(merchant_id=m1.id, title="Mine")
    await make_product(merchant_id=m2.id, title="Theirs")

    async with logged_in_client("m1@shop.com") as mc:
        body = (await mc.get("/merchant/products")).json()
    assert [p["title"] for p in body["items"]] == ["Mine"]


async def test_revenue_summary_counts_delivered_only(client: AsyncClient):
    customer = await make_user("c@shop.com", UserRole.CUSTOMER)
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=merchant.id, price="10.00", stock_qty=100)

    # One delivered order (counts) and one pending order (ignored).
    await make_order(customer_id=customer.id, lines=[(product, 3)], status=OrderStatus.DELIVERED)
    await make_order(customer_id=customer.id, lines=[(product, 5)], status=OrderStatus.PENDING)

    async with logged_in_client("m@shop.com") as mc:
        body = (await mc.get("/merchant/revenue-summary")).json()

    assert body["total_revenue"] == "30.00"  # 3 x 10.00, pending excluded
    assert body["delivered_order_count"] == 1
    assert body["average_order_value"] == "30.00"
    assert body["revenue"]["all_time"] == "30.00"


async def test_revenue_summary_zero_without_delivered_orders(client: AsyncClient):
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    await make_product(merchant_id=merchant.id, price="10.00", stock_qty=5)

    async with logged_in_client("m@shop.com") as mc:
        body = (await mc.get("/merchant/revenue-summary")).json()

    assert body["total_revenue"] == "0"
    assert body["delivered_order_count"] == 0
    assert body["average_order_value"] == "0.00"


async def test_dashboard_shape(client: AsyncClient):
    customer = await make_user("c@shop.com", UserRole.CUSTOMER)
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    top = await make_product(merchant_id=merchant.id, title="Best", price="5.00", stock_qty=100)
    low = await make_product(merchant_id=merchant.id, title="Scarce", price="5.00", stock_qty=2)

    await make_order(customer_id=customer.id, lines=[(top, 10)], status=OrderStatus.DELIVERED)

    async with logged_in_client("m@shop.com") as mc:
        body = (await mc.get("/merchant/dashboard")).json()

    assert body["revenue"]["all_time"] == "50.00"
    assert body["orders_by_status"]["delivered"] == 1
    assert body["orders_by_status"]["pending"] == 0
    assert body["product_count"] == 2
    assert body["top_products"][0]["title"] == "Best"
    assert body["top_products"][0]["units_sold"] == 10
    assert {p["title"] for p in body["low_stock"]} == {"Scarce"}
    assert low.id is not None


async def test_merchant_orders_scoped_and_filterable(client: AsyncClient):
    customer = await make_user("c@shop.com", UserRole.CUSTOMER)
    mine = await make_user("m@shop.com", UserRole.MERCHANT)
    other = await make_user("o@shop.com", UserRole.MERCHANT)
    my_product = await make_product(merchant_id=mine.id, stock_qty=100)
    their_product = await make_product(merchant_id=other.id, stock_qty=100)

    my_delivered = await make_order(
        customer_id=customer.id, lines=[(my_product, 1)], status=OrderStatus.DELIVERED
    )
    await make_order(customer_id=customer.id, lines=[(my_product, 1)], status=OrderStatus.PENDING)
    await make_order(
        customer_id=customer.id, lines=[(their_product, 1)], status=OrderStatus.DELIVERED
    )

    async with logged_in_client("m@shop.com") as mc:
        all_mine = (await mc.get("/merchant/orders")).json()
        assert len(all_mine["items"]) == 2  # only orders containing my product

        delivered = (await mc.get("/merchant/orders", params={"status": "delivered"})).json()
    assert [o["id"] for o in delivered["items"]] == [str(my_delivered.id)]
