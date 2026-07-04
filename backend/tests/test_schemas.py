import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginRequest, RegisterRequest


def test_register_defaults_to_customer():
    req = RegisterRequest(email="a@b.com", password="abcd1234")
    assert req.role == "customer"


def test_register_accepts_merchant():
    req = RegisterRequest(email="a@b.com", password="abcd1234", role="merchant")
    assert req.role == "merchant"


def test_register_rejects_admin_role():
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@b.com", password="abcd1234", role="admin")


def test_register_rejects_short_password():
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@b.com", password="ab1")


def test_register_rejects_password_without_digit():
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@b.com", password="onlyletters")


def test_register_rejects_password_without_letter():
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@b.com", password="12345678")


def test_register_rejects_invalid_email():
    with pytest.raises(ValidationError):
        RegisterRequest(email="not-an-email", password="abcd1234")


def test_login_requires_fields():
    with pytest.raises(ValidationError):
        LoginRequest(email="a@b.com")
