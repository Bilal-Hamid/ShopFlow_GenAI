"""Integration tests for the Reviews endpoint group."""

import uuid

from httpx import AsyncClient

from app.models.user import UserRole
from tests.helpers import logged_in_client, make_product, make_user


async def _product_for_reviews():
    merchant = await make_user("m@shop.com", UserRole.MERCHANT)
    return await make_product(merchant_id=merchant.id)


async def test_customer_can_review_once(client: AsyncClient):
    await make_user("c@shop.com", UserRole.CUSTOMER)
    product = await _product_for_reviews()

    async with logged_in_client("c@shop.com") as cc:
        first = await cc.post(
            f"/products/{product.id}/reviews", json={"rating": 5, "body": "Great"}
        )
        assert first.status_code == 201
        assert first.json()["rating"] == 5

        # Second review by the same customer is a conflict.
        dup = await cc.post(f"/products/{product.id}/reviews", json={"rating": 3})
    assert dup.status_code == 409


async def test_rating_out_of_range_is_422(client: AsyncClient):
    await make_user("c@shop.com", UserRole.CUSTOMER)
    product = await _product_for_reviews()
    async with logged_in_client("c@shop.com") as cc:
        resp = await cc.post(f"/products/{product.id}/reviews", json={"rating": 6})
    assert resp.status_code == 422


async def test_non_customer_cannot_review(client: AsyncClient):
    product = await _product_for_reviews()  # creates the merchant "m@shop.com"
    async with logged_in_client("m@shop.com") as mc:
        resp = await mc.post(f"/products/{product.id}/reviews", json={"rating": 4})
    assert resp.status_code == 403


async def test_review_unknown_product_is_404(client: AsyncClient):
    await make_user("c@shop.com", UserRole.CUSTOMER)
    async with logged_in_client("c@shop.com") as cc:
        resp = await cc.post(f"/products/{uuid.uuid4()}/reviews", json={"rating": 4})
    assert resp.status_code == 404


async def test_list_reviews_public_and_paginated(client: AsyncClient):
    product = await _product_for_reviews()
    for i in range(3):
        await make_user(f"c{i}@shop.com", UserRole.CUSTOMER)
        async with logged_in_client(f"c{i}@shop.com") as cc:
            await cc.post(f"/products/{product.id}/reviews", json={"rating": i + 1})

    first = await client.get(f"/products/{product.id}/reviews", params={"limit": 2})
    body = first.json()
    assert len(body["items"]) == 2
    assert body["nextCursor"] is not None

    second = await client.get(
        f"/products/{product.id}/reviews", params={"limit": 2, "cursor": body["nextCursor"]}
    )
    assert len(second.json()["items"]) == 1


async def test_list_reviews_unknown_product_is_404(client: AsyncClient):
    resp = await client.get(f"/products/{uuid.uuid4()}/reviews")
    assert resp.status_code == 404


async def test_edit_and_delete_permissions(client: AsyncClient):
    await make_user("author@shop.com", UserRole.CUSTOMER)
    await make_user("other@shop.com", UserRole.CUSTOMER)
    await make_user("admin@shop.com", UserRole.ADMIN)
    product = await _product_for_reviews()

    async with logged_in_client("author@shop.com") as ac:
        review_id = (await ac.post(f"/products/{product.id}/reviews", json={"rating": 3})).json()[
            "id"
        ]

    # Non-author cannot edit.
    async with logged_in_client("other@shop.com") as oc:
        forbidden = await oc.patch(f"/reviews/{review_id}", json={"rating": 1})
    assert forbidden.status_code == 403

    # Author can edit.
    async with logged_in_client("author@shop.com") as ac:
        edited = await ac.patch(f"/reviews/{review_id}", json={"rating": 4, "body": "Better"})
    assert edited.status_code == 200
    assert edited.json()["rating"] == 4
    assert edited.json()["body"] == "Better"

    # Admin can delete.
    async with logged_in_client("admin@shop.com") as adm:
        deleted = await adm.delete(f"/reviews/{review_id}")
    assert deleted.status_code == 204

    # Gone now.
    async with logged_in_client("author@shop.com") as ac:
        missing = await ac.patch(f"/reviews/{review_id}", json={"rating": 2})
    assert missing.status_code == 404


async def test_delete_missing_review_is_404(client: AsyncClient):
    await make_user("c@shop.com", UserRole.CUSTOMER)
    async with logged_in_client("c@shop.com") as cc:
        resp = await cc.delete(f"/reviews/{uuid.uuid4()}")
    assert resp.status_code == 404
