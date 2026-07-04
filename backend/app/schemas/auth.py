"""Request/response models for the auth endpoints.

Tokens never appear in these bodies — they are delivered via httpOnly cookies.
Responses expose the authenticated user's public fields only (never the hash).
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import UserRole

# Self-registration is limited to customers and merchants; admins are
# provisioned out-of-band. Kept as a Literal so an invalid role is a 422 at the
# validation layer rather than a runtime check.
RegisterableRole = Literal["customer", "merchant"]

PasswordStr = Annotated[str, Field(min_length=8, max_length=128)]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: PasswordStr
    role: RegisterableRole = "customer"

    @field_validator("password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("password must contain at least one letter and one digit")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    role: UserRole
    created_at: datetime


class MessageResponse(BaseModel):
    message: str
