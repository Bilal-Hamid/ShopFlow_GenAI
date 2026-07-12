"""Reviews business logic.

A customer may leave one review per product (enforced by a unique constraint;
surfaced here as a 409). Reviews are readable publicly for a visible product.
Editing/deleting a review is restricted to its author or an admin. Reviews are
hard-deleted (no soft-delete column on the model).
"""

import uuid
from datetime import datetime

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ProblemException
from app.api.pagination import InvalidCursorError, decode_cursor, encode_cursor
from app.models.review import Review
from app.models.user import User, UserRole
from app.services import product_service


async def create_review(
    db: AsyncSession, *, product_id: uuid.UUID, customer: User, rating: int, body: str | None
) -> Review:
    # Product must exist and be publicly visible to be reviewed.
    await product_service.get_visible_product(db, product_id)

    existing = await db.scalar(
        select(Review.id).where(Review.product_id == product_id, Review.customer_id == customer.id)
    )
    if existing is not None:
        raise ProblemException(
            status_code=409,
            detail="You have already reviewed this product.",
            title="Conflict",
        )

    review = Review(
        product_id=product_id,
        customer_id=customer.id,
        rating=rating,
        body=body,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)
    return review


async def list_reviews(
    db: AsyncSession, *, product_id: uuid.UUID, cursor: str | None, limit: int
) -> tuple[list[Review], str | None]:
    await product_service.get_visible_product(db, product_id)

    stmt = select(Review).where(Review.product_id == product_id)
    if cursor is not None:
        try:
            data = decode_cursor(cursor)
            c_created = datetime.fromisoformat(data["created_at"])
            c_id = uuid.UUID(data["id"])
        except (InvalidCursorError, KeyError, ValueError) as exc:
            raise ProblemException(
                status_code=422,
                detail="Invalid pagination cursor.",
                title="Unprocessable Entity",
            ) from exc
        stmt = stmt.where(tuple_(Review.created_at, Review.id) < tuple_(c_created, c_id))

    stmt = stmt.order_by(Review.created_at.desc(), Review.id.desc()).limit(limit + 1)
    rows = list(await db.scalars(stmt))

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        next_cursor = encode_cursor({"created_at": last.created_at.isoformat(), "id": str(last.id)})
    return rows, next_cursor


async def _load_owned_review(db: AsyncSession, review_id: uuid.UUID, user: User) -> Review:
    review = await db.get(Review, review_id)
    if review is None:
        raise _not_found()
    if user.role != UserRole.ADMIN and review.customer_id != user.id:
        raise ProblemException(
            status_code=403,
            detail="You do not have permission to modify this review.",
            title="Forbidden",
        )
    return review


async def update_review(
    db: AsyncSession,
    *,
    review_id: uuid.UUID,
    user: User,
    rating: int | None,
    body: str | None,
    body_set: bool,
) -> Review:
    review = await _load_owned_review(db, review_id, user)
    if rating is not None:
        review.rating = rating
    if body_set:
        review.body = body
    await db.commit()
    await db.refresh(review)
    return review


async def delete_review(db: AsyncSession, *, review_id: uuid.UUID, user: User) -> None:
    review = await _load_owned_review(db, review_id, user)
    await db.delete(review)
    await db.commit()


def _not_found() -> ProblemException:
    return ProblemException(status_code=404, detail="Review not found.", title="Not Found")
