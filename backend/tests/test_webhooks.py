"""Integration + unit tests for POST /webhooks/payment (Stripe).

Signatures are generated the same way Stripe does — HMAC-SHA256 over
``f"{timestamp}.{payload}"`` with the endpoint signing secret — so the request
exercises the real ``stripe.Webhook.construct_event`` verification path rather
than a mock. The raw bytes signed are the exact bytes sent as the request body.
"""

import hashlib
import hmac
import json
import time
import uuid

from httpx import AsyncClient

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.user import UserRole
from tests.helpers import make_order, make_product, make_user

WEBHOOK_URL = "/webhooks/payment"


def _sign(payload: bytes, *, secret: str | None = None, timestamp: int | None = None) -> str:
    """Build a valid ``Stripe-Signature`` header value for ``payload``."""
    secret = secret or settings.stripe_webhook_secret or ""
    timestamp = timestamp or int(time.time())
    signed_payload = f"{timestamp}.".encode() + payload
    signature = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def _event(
    event_type: str,
    *,
    event_id: str,
    order_id: str | None,
    amount: int | None = None,
    resource: str = "payment_intent",
) -> bytes:
    """Serialize a minimal Stripe event to the exact bytes we'll sign + send."""
    obj: dict = {"id": "pi_or_cs_test", "object": resource}
    if resource == "payment_intent":
        obj["amount"] = amount
        obj["amount_received"] = amount
    else:  # checkout.session
        obj["amount_total"] = amount
        obj["payment_status"] = "paid"
    obj["metadata"] = {"order_id": order_id} if order_id is not None else {}
    event = {"id": event_id, "object": "event", "type": event_type, "data": {"object": obj}}
    return json.dumps(event).encode()


async def _make_pending_order(qty: int = 2, price: str = "10.00", stock_qty: int = 5):
    customer = await make_user("c@shop.com", UserRole.CUSTOMER)
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    product = await make_product(merchant_id=merchant.id, price=price, stock_qty=stock_qty)
    order = await make_order(
        customer_id=customer.id, lines=[(product, qty)], status=OrderStatus.PENDING
    )
    return order, product


async def _order_status(order_id: uuid.UUID) -> OrderStatus:
    async with AsyncSessionLocal() as session:
        return (await session.get(Order, order_id)).status


async def _post(client: AsyncClient, payload: bytes, *, sign: bool = True):
    headers = {"Stripe-Signature": _sign(payload)} if sign else {}
    return await client.post(WEBHOOK_URL, content=payload, headers=headers)


# --------------------------------------------------------------------------- #
# Happy paths
# --------------------------------------------------------------------------- #
async def test_payment_intent_succeeded_confirms_order(client: AsyncClient):
    order, _ = await _make_pending_order(qty=2, price="10.00")  # total 20.00 -> 2000 cents
    payload = _event(
        "payment_intent.succeeded", event_id="evt_1", order_id=str(order.id), amount=2000
    )

    resp = await _post(client, payload)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["outcome"] == "order_confirmed"
    assert body["event_id"] == "evt_1"
    assert await _order_status(order.id) == OrderStatus.CONFIRMED


async def test_checkout_session_completed_confirms_order(client: AsyncClient):
    order, _ = await _make_pending_order(qty=1, price="42.50")  # 4250 cents
    payload = _event(
        "checkout.session.completed",
        event_id="evt_cs",
        order_id=str(order.id),
        amount=4250,
        resource="checkout.session",
    )

    resp = await _post(client, payload)

    assert resp.status_code == 200, resp.text
    assert resp.json()["outcome"] == "order_confirmed"
    assert await _order_status(order.id) == OrderStatus.CONFIRMED


async def test_payment_failed_cancels_and_restocks(client: AsyncClient):
    order, product = await _make_pending_order(qty=2, stock_qty=5)
    payload = _event(
        "payment_intent.payment_failed", event_id="evt_fail", order_id=str(order.id), amount=2000
    )

    resp = await _post(client, payload)

    assert resp.status_code == 200, resp.text
    assert resp.json()["outcome"] == "order_cancelled"
    assert await _order_status(order.id) == OrderStatus.CANCELLED
    async with AsyncSessionLocal() as session:
        # _restock_order returned the 2 ordered units to inventory.
        assert (await session.get(Product, product.id)).stock_qty == 7


# --------------------------------------------------------------------------- #
# Idempotency
# --------------------------------------------------------------------------- #
async def test_duplicate_event_is_ignored(client: AsyncClient):
    order, _ = await _make_pending_order(qty=2, price="10.00")
    payload = _event(
        "payment_intent.succeeded", event_id="evt_dup", order_id=str(order.id), amount=2000
    )

    first = await _post(client, payload)
    second = await _post(client, payload)  # redelivery of the same event id

    assert first.json()["outcome"] == "order_confirmed"
    assert second.status_code == 200
    assert second.json()["outcome"] == "duplicate_ignored"
    assert await _order_status(order.id) == OrderStatus.CONFIRMED


# --------------------------------------------------------------------------- #
# Signature / payload errors
# --------------------------------------------------------------------------- #
async def test_invalid_signature_is_400(client: AsyncClient):
    order, _ = await _make_pending_order()
    payload = _event(
        "payment_intent.succeeded", event_id="evt_bad", order_id=str(order.id), amount=2000
    )

    resp = await client.post(
        WEBHOOK_URL, content=payload, headers={"Stripe-Signature": "t=1,v1=deadbeef"}
    )

    assert resp.status_code == 400
    assert resp.headers["content-type"].startswith("application/problem+json")
    assert await _order_status(order.id) == OrderStatus.PENDING  # untouched


async def test_missing_signature_header_is_400(client: AsyncClient):
    payload = _event("payment_intent.succeeded", event_id="evt_ns", order_id=None)
    resp = await _post(client, payload, sign=False)
    assert resp.status_code == 400
    assert resp.headers["content-type"].startswith("application/problem+json")


async def test_expired_timestamp_is_400(client: AsyncClient):
    payload = _event("payment_intent.succeeded", event_id="evt_old", order_id=None)
    stale = int(time.time()) - 10_000  # well outside the 300s tolerance
    resp = await client.post(
        WEBHOOK_URL, content=payload, headers={"Stripe-Signature": _sign(payload, timestamp=stale)}
    )
    assert resp.status_code == 400


async def test_unconfigured_secret_is_500(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "stripe_webhook_secret", None)
    payload = _event("payment_intent.succeeded", event_id="evt_cfg", order_id=None)
    # Signature is irrelevant here — the missing secret is caught first.
    resp = await client.post(WEBHOOK_URL, content=payload, headers={"Stripe-Signature": "t=1,v1=x"})
    assert resp.status_code == 500
    assert resp.headers["content-type"].startswith("application/problem+json")


# --------------------------------------------------------------------------- #
# Verified events that don't map to an actionable transition (still 2xx)
# --------------------------------------------------------------------------- #
async def test_amount_mismatch_leaves_order_pending(client: AsyncClient):
    order, _ = await _make_pending_order(qty=2, price="10.00")  # expects 2000
    payload = _event(
        "payment_intent.succeeded", event_id="evt_mm", order_id=str(order.id), amount=999
    )

    resp = await _post(client, payload)

    assert resp.status_code == 200
    assert resp.json()["outcome"] == "amount_mismatch"
    assert await _order_status(order.id) == OrderStatus.PENDING


async def test_unknown_order_is_acknowledged(client: AsyncClient):
    payload = _event(
        "payment_intent.succeeded",
        event_id="evt_unknown",
        order_id=str(uuid.uuid4()),
        amount=2000,
    )
    resp = await _post(client, payload)
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "order_not_found"


async def test_missing_order_reference_is_acknowledged(client: AsyncClient):
    payload = _event("payment_intent.succeeded", event_id="evt_noref", order_id=None, amount=2000)
    resp = await _post(client, payload)
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "no_order_reference"


async def test_unhandled_event_type_is_acknowledged(client: AsyncClient):
    payload = _event("payment_intent.created", event_id="evt_ignore", order_id=None)
    resp = await _post(client, payload)
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "unhandled"


async def test_malformed_json_payload_is_400(client: AsyncClient):
    payload = b"{not valid json"
    resp = await client.post(
        WEBHOOK_URL, content=payload, headers={"Stripe-Signature": _sign(payload)}
    )
    assert resp.status_code == 400
    assert resp.headers["content-type"].startswith("application/problem+json")


async def test_malformed_order_id_is_acknowledged(client: AsyncClient):
    payload = _event(
        "payment_intent.succeeded", event_id="evt_badid", order_id="not-a-uuid", amount=2000
    )
    resp = await _post(client, payload)
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "no_order_reference"


async def test_success_on_already_confirmed_order_is_idempotent(client: AsyncClient):
    order, _ = await _make_pending_order(qty=2, price="10.00")
    async with AsyncSessionLocal() as session:
        (await session.get(Order, order.id)).status = OrderStatus.CONFIRMED
        await session.commit()

    # A distinct event id (not a redelivery) targeting an order already past pending.
    payload = _event(
        "payment_intent.succeeded", event_id="evt_ac", order_id=str(order.id), amount=2000
    )
    resp = await _post(client, payload)

    assert resp.status_code == 200
    assert resp.json()["outcome"] == "already_confirmed"
    assert await _order_status(order.id) == OrderStatus.CONFIRMED


async def test_success_on_cancelled_order_does_not_resurrect(client: AsyncClient):
    order, _ = await _make_pending_order(qty=2, price="10.00")
    async with AsyncSessionLocal() as session:
        (await session.get(Order, order.id)).status = OrderStatus.CANCELLED
        await session.commit()

    payload = _event(
        "payment_intent.succeeded", event_id="evt_res", order_id=str(order.id), amount=2000
    )
    resp = await _post(client, payload)

    assert resp.status_code == 200
    assert resp.json()["outcome"] == "order_cancelled_already"
    assert await _order_status(order.id) == OrderStatus.CANCELLED


async def test_failure_on_non_pending_order_is_noop(client: AsyncClient):
    order, product = await _make_pending_order(qty=2, stock_qty=5)
    async with AsyncSessionLocal() as session:
        (await session.get(Order, order.id)).status = OrderStatus.SHIPPED
        await session.commit()

    payload = _event(
        "payment_intent.payment_failed", event_id="evt_lf", order_id=str(order.id), amount=2000
    )
    resp = await _post(client, payload)

    assert resp.status_code == 200
    assert resp.json()["outcome"] == "already_finalized"
    assert await _order_status(order.id) == OrderStatus.SHIPPED
    async with AsyncSessionLocal() as session:
        assert (await session.get(Product, product.id)).stock_qty == 5  # not restocked
