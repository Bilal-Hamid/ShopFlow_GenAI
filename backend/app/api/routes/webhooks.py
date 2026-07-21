"""Payment webhooks (Stripe).

``POST /webhooks/payment`` is authenticated by the Stripe signature rather than
JWT: there is no ``Depends`` on ``get_current_user`` here. The endpoint reads the
raw request body (required for signature verification), verifies it, deduplicates
by event id, and applies the resulting order state transition.

No IP rate limiter is applied. The signature is the authentication, and Stripe
legitimately bursts deliveries; throttling by source IP would drop genuine
events. Unverified requests are rejected with a 400 before any work is done.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.problem import ProblemDetail
from app.schemas.webhook import WebhookAck
from app.services import payment_service

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "/payment",
    response_model=WebhookAck,
    summary="Receive Stripe payment events (signature-verified)",
    responses={
        400: {"model": ProblemDetail, "description": "Missing or invalid signature/payload"},
        500: {"model": ProblemDetail, "description": "Webhook not configured"},
    },
)
async def stripe_payment_webhook(
    request: Request,
    db: DbSession,
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> WebhookAck:
    payload = await request.body()
    event = payment_service.verify_event(payload, stripe_signature)

    # Idempotency: a redelivery of an already-processed event is a no-op.
    if not await payment_service._claim_event(event["id"]):
        return WebhookAck(
            event_id=event["id"], event_type=event["type"], outcome="duplicate_ignored"
        )

    outcome = await payment_service.handle_event(db, event)
    return WebhookAck(event_id=event["id"], event_type=event["type"], outcome=outcome)
