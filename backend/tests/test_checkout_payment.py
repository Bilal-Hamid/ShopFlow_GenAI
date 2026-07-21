"""Tests for Stripe payment initiation at checkout, and the full
checkout -> webhook -> order-confirmed loop.

The Stripe API call is stubbed at ``payment_service._stripe_create_session`` so
these tests exercise our parameter-building and wiring without hitting the
network. The end-to-end test then feeds a signed event into the real webhook to
prove the two halves connect.
"""

import types
import uuid

import stripe
from httpx import AsyncClient

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.order import Order, OrderStatus
from app.models.user import UserRole
from app.services import payment_service
from tests.helpers import logged_in_client, make_product, make_user
from tests.test_webhooks import _event, _sign

_ADDRESS = {
    "full_name": "Grace Hopper",
    "line1": "1 Compiler Ct",
    "city": "Arlington",
    "postal_code": "22201",
    "country": "US",
}


async def _add_and_checkout(cc: AsyncClient, product_id: uuid.UUID, qty: int):
    resp = await cc.post("/cart/items", json={"product_id": str(product_id), "quantity": qty})
    assert resp.status_code == 201, resp.text
    return await cc.post("/orders/checkout", json={"shipping_address": _ADDRESS})


async def _enable_stripe(monkeypatch, session_factory):
    """Configure a dummy key and stub the Stripe session-creation call."""
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_dummy")
    monkeypatch.setattr(payment_service, "_stripe_create_session", session_factory)


async def test_checkout_without_stripe_has_no_payment_url(client: AsyncClient):
    # settings.stripe_secret_key is unset in the test env -> order still created.
    await make_user("c@shop.com", UserRole.CUSTOMER)
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=merchant.id, price="10.00", stock_qty=5)

    async with logged_in_client("c@shop.com") as cc:
        resp = await _add_and_checkout(cc, product.id, 2)

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["payment_url"] is None


async def test_checkout_with_stripe_creates_session(client: AsyncClient, monkeypatch):
    captured: dict = {}

    async def fake_create(params):
        captured.update(params)
        return types.SimpleNamespace(url="https://pay.stripe.test/cs_test_1", id="cs_test_1")

    await _enable_stripe(monkeypatch, fake_create)

    await make_user("c@shop.com", UserRole.CUSTOMER)
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=merchant.id, price="10.00", stock_qty=5)

    async with logged_in_client("c@shop.com") as cc:
        resp = await _add_and_checkout(cc, product.id, 2)  # total 20.00 -> 2000 cents

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["payment_url"] == "https://pay.stripe.test/cs_test_1"

    # The session is built for the order total, tagged with the order id on both
    # the session and the PaymentIntent, and lets Stripe pick payment methods.
    assert captured["mode"] == "payment"
    assert "payment_method_types" not in captured
    assert captured["line_items"][0]["price_data"]["unit_amount"] == 2000
    assert captured["metadata"]["order_id"] == body["id"]
    assert captured["payment_intent_data"]["metadata"]["order_id"] == body["id"]


async def test_checkout_stripe_error_is_502(client: AsyncClient, monkeypatch):
    async def boom(params):
        raise stripe.StripeError("provider down")

    await _enable_stripe(monkeypatch, boom)

    await make_user("c@shop.com", UserRole.CUSTOMER)
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=merchant.id, price="10.00", stock_qty=5)

    async with logged_in_client("c@shop.com") as cc:
        resp = await _add_and_checkout(cc, product.id, 1)

    assert resp.status_code == 502
    assert resp.headers["content-type"].startswith("application/problem+json")


async def test_end_to_end_checkout_then_webhook_confirms(client: AsyncClient, monkeypatch):
    async def fake_create(params):
        return types.SimpleNamespace(url="https://pay.stripe.test/cs_e2e", id="cs_e2e")

    await _enable_stripe(monkeypatch, fake_create)

    await make_user("c@shop.com", UserRole.CUSTOMER)
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=merchant.id, price="10.00", stock_qty=5)

    async with logged_in_client("c@shop.com") as cc:
        resp = await _add_and_checkout(cc, product.id, 2)  # total 20.00
    order_id = resp.json()["id"]
    assert resp.json()["status"] == "pending"

    # Stripe calls our webhook once the customer pays on the hosted page.
    payload = _event("payment_intent.succeeded", event_id="evt_e2e", order_id=order_id, amount=2000)
    webhook = await client.post(
        "/webhooks/payment", content=payload, headers={"Stripe-Signature": _sign(payload)}
    )

    assert webhook.status_code == 200, webhook.text
    assert webhook.json()["outcome"] == "order_confirmed"
    async with AsyncSessionLocal() as session:
        order = await session.get(Order, uuid.UUID(order_id))
        assert order.status == OrderStatus.CONFIRMED
