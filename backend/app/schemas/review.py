"""Request/response models for the Reviews endpoint group.

Rating is constrained to 1-5 (mirroring the DB check constraint). One review per
customer per product is enforced by a unique constraint; the service surfaces a
duplicate as a 409.
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Rating = Annotated[int, Field(ge=1, le=5)]
Body = Annotated[str, Field(max_length=5000)]


class ReviewCreate(BaseModel):
    rating: Rating
    body: Body | None = None


class ReviewUpdate(BaseModel):
    rating: Rating | None = None
    body: Body | None = None


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    customer_id: uuid.UUID
    rating: int
    body: str | None
    created_at: datetime
