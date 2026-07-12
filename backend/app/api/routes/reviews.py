"""Reviews endpoints.

Product-scoped routes live under ``/products/{id}/reviews``; direct edits/deletes
live under ``/reviews/{id}``. Reading reviews is public (rate-limited per IP);
creating requires a customer, and editing/deleting requires the author or an
admin (rate-limited per user).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, authenticated_rate_limiter, require_roles
from app.api.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.api.rate_limit import public_rate_limiter
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.problem import ProblemDetail
from app.schemas.review import ReviewCreate, ReviewResponse, ReviewUpdate
from app.services import review_service

router = APIRouter(tags=["reviews"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
Limit = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
CustomerUser = Annotated[User, Depends(require_roles(UserRole.CUSTOMER))]


@router.post(
    "/products/{product_id}/reviews",
    status_code=status.HTTP_201_CREATED,
    response_model=ReviewResponse,
    summary="Review a product (customer, one per product)",
    dependencies=[Depends(authenticated_rate_limiter)],
    responses={
        403: {"model": ProblemDetail, "description": "Not a customer"},
        404: {"model": ProblemDetail, "description": "Product not found"},
        409: {"model": ProblemDetail, "description": "Already reviewed"},
    },
)
async def create_review(
    product_id: uuid.UUID, payload: ReviewCreate, db: DbSession, customer: CustomerUser
) -> ReviewResponse:
    return await review_service.create_review(
        db, product_id=product_id, customer=customer, rating=payload.rating, body=payload.body
    )


@router.get(
    "/products/{product_id}/reviews",
    response_model=Page[ReviewResponse],
    summary="List a product's reviews (cursor-paginated)",
    dependencies=[Depends(public_rate_limiter)],
    responses={404: {"model": ProblemDetail, "description": "Product not found"}},
)
async def list_reviews(
    product_id: uuid.UUID,
    db: DbSession,
    cursor: str | None = None,
    limit: Limit = DEFAULT_PAGE_SIZE,
) -> Page[ReviewResponse]:
    items, next_cursor = await review_service.list_reviews(
        db, product_id=product_id, cursor=cursor, limit=limit
    )
    return Page(items=items, next_cursor=next_cursor)


@router.patch(
    "/reviews/{review_id}",
    response_model=ReviewResponse,
    summary="Edit a review (author or admin)",
    dependencies=[Depends(authenticated_rate_limiter)],
    responses={
        403: {"model": ProblemDetail, "description": "Not the author"},
        404: {"model": ProblemDetail, "description": "Review not found"},
    },
)
async def update_review(
    review_id: uuid.UUID, payload: ReviewUpdate, db: DbSession, user: CurrentUser
) -> ReviewResponse:
    return await review_service.update_review(
        db,
        review_id=review_id,
        user=user,
        rating=payload.rating,
        body=payload.body,
        body_set="body" in payload.model_fields_set,
    )


@router.delete(
    "/reviews/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a review (author or admin)",
    dependencies=[Depends(authenticated_rate_limiter)],
    responses={
        403: {"model": ProblemDetail, "description": "Not the author"},
        404: {"model": ProblemDetail, "description": "Review not found"},
    },
)
async def delete_review(review_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Response:
    await review_service.delete_review(db, review_id=review_id, user=user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
