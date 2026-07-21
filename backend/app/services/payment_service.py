"""Stripe payment integration: creating hosted Checkout Sessions at checkout
(outbound), and the webhook business logic that reacts to payment events
(inbound) — signature verification, idempotency, and order state transitions.

Outbound (checkout)
-------------------
``create_checkout_session`` turns a pending order into a Stripe-hosted payment
page. The order id is stamped into the session *and* the underlying
PaymentIntent metadata so that whichever event Stripe later sends carries the
reference the webhook needs. ``payment_method_types`` is deliberately omitted to
enable dynamic payment methods (Stripe picks the best methods per customer).

Trust model
-----------
The webhook is authenticated by the Stripe signature (not JWT). We verify the
``Stripe-Signature`` header against the endpoint's signing secret with the
Stripe SDK, which also rejects payloads outside a 5-minute timestamp tolerance
(replay protection). Only after verification do we act on the event.

Order linkage
-------------
Payments are tied to orders via ``metadata.order_id`` set on the PaymentIntent /
Checkout Session when the payment is created at checkout time. The webhook reads
that id, matches the paid amount against ``order.total_amount`` as a tamper check,
and advances the order:

- payment succeeded -> order ``pending`` becomes ``confirmed``
- payment failed    -> order ``pending`` becomes ``cancelled`` (stock restocked)

Idempotency
-----------
Stripe delivers events at-least-once and retries on non-2xx. We record each
processed ``event.id`` in Redis (``SET NX``) so a redelivery is a no-op, and we
return 2xx for events we don't act on so Stripe stops retrying them.
"""

import logging
import secrets
import string
import uuid
from decimal import Decimal

import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ProblemException
from app.core.config import settings
from app.db.redis import redis_client
from app.models.order import Order, OrderStatus
from app.services import order_service

logger = logging.getLogger(__name__)

# Stripe retries a failing webhook for up to ~3 days; keep the dedupe marker a
# little longer so a late redelivery is still recognised as a duplicate.
_EVENT_TTL_SECONDS = 7 * 24 * 60 * 60

# Event types this endpoint acts on. Anything else is acknowledged (200) and
# ignored so Stripe doesn't keep retrying it.
_SUCCESS_TYPES = frozenset(
    {
        "payment_intent.succeeded",
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    }
)
_FAILURE_TYPES = frozenset(
    {
        "payment_intent.payment_failed",
        "checkout.session.async_payment_failed",
    }
)


# --------------------------------------------------------------------------- #
# Signature verification
# --------------------------------------------------------------------------- #
def verify_event(payload: bytes, sig_header: str | None) -> stripe.Event:
    """Verify the raw request against the Stripe signature, returning the event.

    Raises ``ProblemException`` (400) on a missing/invalid signature and (500)
    if the webhook secret is not configured on the server.
    """
    secret = settings.stripe_webhook_secret
    if not secret:
        logger.error("Stripe webhook received but STRIPE_WEBHOOK_SECRET is not configured.")
        raise ProblemException(
            status_code=500,
            detail="Payment webhook is not configured.",
            title="Internal Server Error",
        )
    if not sig_header:
        raise ProblemException(
            status_code=400,
            detail="Missing Stripe-Signature header.",
            title="Bad Request",
        )
    try:
        return stripe.Webhook.construct_event(payload, sig_header, secret)
    except stripe.SignatureVerificationError as exc:
        raise ProblemException(
            status_code=400,
            detail="Signature verification failed.",
            title="Bad Request",
        ) from exc
    except ValueError as exc:  # malformed JSON payload
        raise ProblemException(
            status_code=400,
            detail="Invalid payload.",
            title="Bad Request",
        ) from exc


# --------------------------------------------------------------------------- #
# Idempotency
# --------------------------------------------------------------------------- #
async def _claim_event(event_id: str) -> bool:
    """Atomically record ``event_id`` as processed. True if this is the first
    time we've seen it (caller should process); False if it's a redelivery."""
    claimed = await redis_client.set(
        f"stripe:webhook:event:{event_id}", "1", nx=True, ex=_EVENT_TTL_SECONDS
    )
    return bool(claimed)


# --------------------------------------------------------------------------- #
# Event handling
# --------------------------------------------------------------------------- #
def _get(obj: stripe.StripeObject, key: str):
    """Safe key lookup on a StripeObject (which supports subscript but not
    ``.get()`` in the current SDK); returns None when the key is absent."""
    try:
        return obj[key]
    except KeyError, TypeError:
        return None


def _extract_reference(obj: stripe.StripeObject) -> tuple[str | None, int | None]:
    """Pull (order_id, paid amount in cents) out of a PaymentIntent or Checkout
    Session object. Returns (None, ...) when no order reference is present."""
    metadata = _get(obj, "metadata")
    order_id = _get(metadata, "order_id") if metadata is not None else None
    # PaymentIntent -> amount_received; Checkout Session -> amount_total.
    amount = _get(obj, "amount_received")
    if amount is None:
        amount = _get(obj, "amount_total")
    if amount is None:
        amount = _get(obj, "amount")
    return order_id, amount


def _to_cents(amount: Decimal) -> int:
    """Convert a major-unit money amount to integer minor units (cents)."""
    return int((amount * 100).to_integral_value())


def _amount_matches(order: Order, amount_cents: int | None) -> bool:
    if amount_cents is None:
        return True  # nothing to compare against; trust the verified event
    return amount_cents == _to_cents(order.total_amount)


async def handle_event(db: AsyncSession, event: stripe.Event) -> str:
    """Dispatch a verified, non-duplicate event to the right order transition.

    Returns a short outcome string (surfaced in the ack body / logs). Callers
    should have already claimed the event for idempotency.
    """
    event_type = event["type"]
    if event_type not in _SUCCESS_TYPES and event_type not in _FAILURE_TYPES:
        return "unhandled"

    obj = event["data"]["object"]
    order_id_str, amount_cents = _extract_reference(obj)
    if not order_id_str:
        logger.warning("Stripe event %s (%s) has no metadata.order_id.", event["id"], event_type)
        return "no_order_reference"

    try:
        order_id = uuid.UUID(order_id_str)
    except ValueError:
        logger.warning("Stripe event %s has malformed order_id %r.", event["id"], order_id_str)
        return "no_order_reference"

    order = await db.get(Order, order_id)
    if order is None:
        logger.warning("Stripe event %s references unknown order %s.", event["id"], order_id)
        return "order_not_found"

    if event_type in _SUCCESS_TYPES:
        return await _apply_success(db, order, amount_cents, event)
    return await _apply_failure(db, order)


async def _apply_success(
    db: AsyncSession, order: Order, amount_cents: int | None, event: stripe.Event
) -> str:
    if order.status == OrderStatus.CANCELLED:
        # Payment landed on an order we already cancelled — don't resurrect it.
        logger.warning(
            "Stripe event %s: payment for already-cancelled order %s.", event["id"], order.id
        )
        return "order_cancelled_already"
    if order.status != OrderStatus.PENDING:
        return "already_confirmed"  # idempotent: already past pending

    if not _amount_matches(order, amount_cents):
        # A verified event whose amount doesn't match the order is a red flag;
        # refuse to confirm and leave the order pending for manual review.
        logger.error(
            "Stripe event %s: amount %s cents != order %s total %s.",
            event["id"],
            amount_cents,
            order.id,
            order.total_amount,
        )
        return "amount_mismatch"

    order.status = OrderStatus.CONFIRMED
    await db.commit()
    return "order_confirmed"


async def _apply_failure(db: AsyncSession, order: Order) -> str:
    if order.status != OrderStatus.PENDING:
        return "already_finalized"  # can't cancel a shipped/delivered/cancelled order
    await order_service._restock_order(db, order.id)
    order.status = OrderStatus.CANCELLED
    await db.commit()
    return "order_cancelled"


# --------------------------------------------------------------------------- #
# Outbound: create a hosted Checkout Session for a pending order
# --------------------------------------------------------------------------- #
_client: stripe.StripeClient | None = None


def _get_client() -> stripe.StripeClient:
    """Lazily build the module-level Stripe client from the configured key."""
    global _client
    if _client is None:
        if not settings.stripe_secret_key:
            raise ProblemException(
                status_code=500,
                detail="Payments are not configured.",
                title="Internal Server Error",
            )
        _client = stripe.StripeClient(
            settings.stripe_secret_key, stripe_version=settings.stripe_api_version
        )
    return _client


def _integration_identifier() -> str:
    # Skill convention: a stable label plus an 8-random-letter suffix so
    # different checkout flows can be compared in the Stripe Dashboard.
    suffix = "".join(secrets.choice(string.ascii_lowercase) for _ in range(8))
    return f"shopflow-checkout-{suffix}"


async def _stripe_create_session(params: dict) -> stripe.checkout.Session:
    """Thin wrapper around the Stripe API call (isolated so tests can stub it)."""
    return await _get_client().v1.checkout.sessions.create_async(params=params)


async def create_checkout_session(*, order_id: uuid.UUID, amount: Decimal) -> str:
    """Create a Stripe-hosted Checkout Session for a pending order and return its
    payment URL. Raises ``ProblemException`` (502) if Stripe rejects the call.

    The whole order total is charged as a single line item so the amount always
    matches ``order.total_amount`` (coupons are already applied to the total);
    the webhook's amount check relies on that equality.
    """
    base = settings.frontend_base_url.rstrip("/")
    # {CHECKOUT_SESSION_ID} is a Stripe template literal it substitutes on redirect.
    success_url = f"{base}/checkout/success?order_id={order_id}&session_id={{CHECKOUT_SESSION_ID}}"
    params = {
        "mode": "payment",
        "line_items": [
            {
                "price_data": {
                    "currency": settings.payment_currency,
                    "product_data": {"name": f"ShopFlow order {order_id}"},
                    "unit_amount": _to_cents(amount),
                },
                "quantity": 1,
            }
        ],
        # Stamp the order id on both the session and the PaymentIntent so the
        # reference survives whichever event type Stripe delivers to the webhook.
        "metadata": {"order_id": str(order_id)},
        "payment_intent_data": {"metadata": {"order_id": str(order_id)}},
        "success_url": success_url,
        "cancel_url": f"{base}/checkout/cancel?order_id={order_id}",
        "integration_identifier": _integration_identifier(),
    }
    try:
        session = await _stripe_create_session(params)
    except stripe.StripeError as exc:
        logger.error("Stripe checkout session creation failed for order %s: %s", order_id, exc)
        raise ProblemException(
            status_code=502,
            detail="Could not initiate payment with the payment provider.",
            title="Bad Gateway",
        ) from exc
    return session.url
