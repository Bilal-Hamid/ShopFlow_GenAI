"""Response model for the Stripe payment webhook.

The *request* body for this endpoint is intentionally not a Pydantic model: the
raw request bytes are required verbatim to verify the Stripe signature, so the
payload is read as bytes and parsed by the Stripe SDK. The response below is a
small acknowledgement returned to Stripe (Stripe only cares about the 2xx status
code; the body is informational and useful for debugging via the Dashboard).
"""

from typing import Literal

from pydantic import BaseModel


class WebhookAck(BaseModel):
    received: Literal[True] = True
    event_id: str | None = None
    event_type: str | None = None
    # What the handler did with the event, e.g. "order_confirmed",
    # "order_cancelled", "duplicate_ignored", "unhandled", "amount_mismatch",
    # "order_not_found", "no_order_reference".
    outcome: str
