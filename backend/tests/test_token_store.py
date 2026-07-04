"""Refresh-token family behaviour against real Redis (rotation + reuse)."""

from app.services import token_store


async def test_start_and_rotate_valid():
    fid = "family-1"
    await token_store.start_family(fid, "jti-1")

    rotated = await token_store.rotate(fid, "jti-1", "jti-2")
    assert rotated is True

    # The new jti is now the live member; rotating it again works.
    assert await token_store.rotate(fid, "jti-2", "jti-3") is True


async def test_reuse_of_consumed_token_burns_family():
    fid = "family-2"
    await token_store.start_family(fid, "jti-1")
    assert await token_store.rotate(fid, "jti-1", "jti-2") is True

    # Replaying the already-consumed jti-1 must fail and revoke the whole family.
    assert await token_store.rotate(fid, "jti-1", "jti-x") is False

    # Family is gone: the previously-valid jti-2 can no longer rotate.
    assert await token_store.rotate(fid, "jti-2", "jti-3") is False


async def test_rotate_unknown_family_returns_false():
    assert await token_store.rotate("no-such-family", "a", "b") is False


async def test_revoke_family():
    fid = "family-3"
    await token_store.start_family(fid, "jti-1")
    await token_store.revoke_family(fid)
    assert await token_store.rotate(fid, "jti-1", "jti-2") is False
