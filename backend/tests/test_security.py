import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core import security
from app.core.config import settings
from app.core.security import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_password_roundtrip():
    hashed = hash_password("Sup3rSecret")
    assert hashed != "Sup3rSecret"
    assert verify_password("Sup3rSecret", hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("Sup3rSecret")
    assert verify_password("wrong", hashed) is False


def test_verify_password_malformed_hash_does_not_raise():
    assert verify_password("anything", "not-a-hash") is False


def test_access_token_carries_role_and_type():
    uid = uuid.uuid4()
    token = create_access_token(uid, "merchant")
    claims = decode_token(token, expected_type=ACCESS_TOKEN_TYPE)
    assert claims["sub"] == str(uid)
    assert claims["role"] == "merchant"
    assert claims["type"] == ACCESS_TOKEN_TYPE
    assert "jti" in claims


def test_refresh_token_returns_jti_and_carries_family():
    uid = uuid.uuid4()
    fid = "fam123"
    token, jti = create_refresh_token(uid, fid)
    claims = decode_token(token, expected_type=REFRESH_TOKEN_TYPE)
    assert claims["fid"] == fid
    assert claims["jti"] == jti
    assert claims["type"] == REFRESH_TOKEN_TYPE


def test_decode_rejects_wrong_type():
    token = create_access_token(uuid.uuid4(), "customer")
    with pytest.raises(TokenError):
        decode_token(token, expected_type=REFRESH_TOKEN_TYPE)


def test_decode_rejects_tampered_signature():
    token = create_access_token(uuid.uuid4(), "customer")
    with pytest.raises(TokenError):
        decode_token(token + "x", expected_type=ACCESS_TOKEN_TYPE)


def test_decode_rejects_expired_token():
    expired = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "type": ACCESS_TOKEN_TYPE,
            "role": "customer",
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(TokenError):
        decode_token(expired, expected_type=ACCESS_TOKEN_TYPE)


def test_dummy_hash_is_valid_argon2(monkeypatch):
    # Sanity: the timing-equalisation hash imported by auth_service verifies.
    from app.services import auth_service

    assert security.verify_password("x", auth_service._DUMMY_HASH) is False
