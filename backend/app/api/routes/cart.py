"""Cart endpoints (customer-only, authenticated).

The cart is Redis-backed and scoped to the authenticated customer; all routes
are rate-limited per user. ``item_id`` in the item routes is the product's id —
the cart is keyed by product, so there is no separate line-item id.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import authenticated_rate_limiter, require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.cart import CartItemAdd, CartItemUpdate, CartResponse
from app.schemas.problem import ProblemDetail
from app.services import cart_service

router = APIRouter(
    prefix="/cart",
    tags=["cart"],
    dependencies=[Depends(authenticated_rate_limiter)],
    responses={
        403: {"model": ProblemDetail, "description": "Not a customer"},
        429: {"model": ProblemDetail, "description": "Rate limit exceeded"},
    },
)

DbSession = Annotated[AsyncSession, Depends(get_db)]
CustomerUser = Annotated[User, Depends(require_roles(UserRole.CUSTOMER))]


@router.get("", response_model=CartResponse, summary="Get the current cart")
async def get_cart(db: DbSession, customer: CustomerUser) -> CartResponse:
    return await cart_service.get_cart(db, user_id=customer.id)


@router.post(
    "/items",
    status_code=status.HTTP_201_CREATED,
    response_model=CartResponse,
    summary="Add an item to the cart (or increase its quantity)",
    responses={
        404: {"model": ProblemDetail, "description": "Product not found"},
        409: {"model": ProblemDetail, "description": "Insufficient stock"},
    },
)
async def add_item(payload: CartItemAdd, db: DbSession, customer: CustomerUser) -> CartResponse:
    return await cart_service.add_item(
        db, user_id=customer.id, product_id=payload.product_id, quantity=payload.quantity
    )


@router.patch(
    "/items/{item_id}",
    response_model=CartResponse,
    summary="Set the quantity of a cart item",
    responses={
        404: {"model": ProblemDetail, "description": "Item not in cart"},
        409: {"model": ProblemDetail, "description": "Insufficient stock"},
    },
)
async def update_item(
    item_id: uuid.UUID, payload: CartItemUpdate, db: DbSession, customer: CustomerUser
) -> CartResponse:
    return await cart_service.update_item(
        db, user_id=customer.id, product_id=item_id, quantity=payload.quantity
    )


@router.delete(
    "/items/{item_id}",
    response_model=CartResponse,
    summary="Remove an item from the cart",
    responses={404: {"model": ProblemDetail, "description": "Item not in cart"}},
)
async def remove_item(item_id: uuid.UUID, db: DbSession, customer: CustomerUser) -> CartResponse:
    return await cart_service.remove_item(db, user_id=customer.id, product_id=item_id)


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Empty the cart",
)
async def clear_cart(customer: CustomerUser) -> Response:
    await cart_service.clear_cart(customer.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
