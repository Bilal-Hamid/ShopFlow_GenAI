"""Cursor-based (keyset) pagination primitives shared by all list endpoints.

Standards requirement: every list-returning endpoint uses cursor-based
pagination and returns ``nextCursor`` — no offset/page-number pagination.

The cursor is an **opaque**, URL-safe base64 blob wrapping a small JSON object
whose shape is chosen per entity (e.g. ``{"id": ...}`` for products, or
``{"created_at": ..., "id": ...}`` for time-ordered entities). Callers must
treat it as opaque; only these helpers encode/decode it. A malformed cursor
raises ``InvalidCursorError`` so routes can turn it into a 422.
"""

import base64
import binascii
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class InvalidCursorError(ValueError):
    """Raised when a client-supplied cursor cannot be decoded."""


def encode_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(cursor: str) -> dict[str, Any]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        data = json.loads(raw)
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise InvalidCursorError("Malformed pagination cursor.") from exc
    if not isinstance(data, dict):
        raise InvalidCursorError("Malformed pagination cursor.")
    return data


class Page[T](BaseModel):
    """Generic paginated envelope. Serializes the cursor as ``nextCursor``."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[T]
    next_cursor: str | None = Field(default=None, alias="nextCursor")
