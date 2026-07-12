"""Request/response models for the Admin endpoint group.

``AdminUserResponse`` exposes user rows to admins including ``deleted_at`` (so
deactivated accounts are visible) but never the password hash. ``AdminUserUpdate``
doubles as a recovery flow: an admin may reset a user's email/password, change
their role, and deactivate/reactivate them. Password changes are validated with
the same strength rules as self-registration and are Argon2-hashed in the
service — plaintext never reaches the DB.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.user import UserRole
from app.schemas.merchant import RevenueWindows

PasswordStr = Annotated[str, Field(min_length=8, max_length=128)]


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    role: UserRole
    created_at: datetime
    deleted_at: datetime | None


class AdminUserUpdate(BaseModel):
    """PATCH — every field optional; at least one must be provided.

    ``is_active`` toggles the soft-delete state: ``False`` deactivates (sets
    ``deleted_at``), ``True`` reactivates (clears it).
    """

    email: EmailStr | None = None
    password: PasswordStr | None = None
    role: UserRole | None = None
    is_active: bool | None = None

    @field_validator("password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("password must contain at least one letter and one digit")
        return value

    @model_validator(mode="after")
    def _at_least_one_field(self) -> AdminUserUpdate:
        if (
            self.email is None
            and self.password is None
            and self.role is None
            and self.is_active is None
        ):
            raise ValueError("at least one field must be provided")
        return self


class PlatformStats(BaseModel):
    total_users: int
    users_by_role: dict[str, int]
    total_products: int
    products_by_status: dict[str, int]
    total_orders: int
    orders_by_status: dict[str, int]
    total_revenue: Decimal
    revenue: RevenueWindows
