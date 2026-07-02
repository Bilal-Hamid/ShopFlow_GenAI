import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPKMixin
from app.db.enum_utils import enum_values as _enum_values


class DiscountType(enum.StrEnum):
    PERCENT = "percent"
    FLAT = "flat"


class Coupon(UUIDPKMixin, Base):
    __tablename__ = "coupons"
    __table_args__ = (
        CheckConstraint("value > 0", name="ck_coupons_value_positive"),
        CheckConstraint(
            "discount_type != 'percent' OR value <= 100",
            name="ck_coupons_percent_value_max_100",
        ),
        CheckConstraint(
            "usage_limit IS NULL OR usage_limit > 0", name="ck_coupons_usage_limit_positive"
        ),
    )

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    discount_type: Mapped[DiscountType] = mapped_column(
        Enum(DiscountType, name="discount_type", native_enum=True, values_callable=_enum_values),
        nullable=False,
    )
    value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    usage_limit: Mapped[int | None] = mapped_column(nullable=True)
