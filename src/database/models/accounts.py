import enum
from datetime import datetime, date, timedelta, timezone
from typing import List, Optional

from sqlalchemy import (
    String,
    Boolean,
    ForeignKey,
    Text,
    Date,
    Enum,
    DateTime,
    func,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from src.database.session import Base

from src.security.passwords import hash_password, verify_password


class UserGroupEnum(str, enum.Enum):
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class GenderEnum(str, enum.Enum):
    MAN = "man"
    WOMAN = "woman"


class TokenBase(Base):
    __abstract__ = True
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc) + timedelta(days=1),
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )


class UserGroup(Base):
    __tablename__ = "user_groups"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[UserGroupEnum] = mapped_column(
        Enum(UserGroupEnum), unique=True, nullable=False
    )

    users: Mapped[List["User"]] = relationship(back_populates="group")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )

    _hashed_password: Mapped[str] = mapped_column(
        "hashed_password", String(255), nullable=False
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    group_id: Mapped[int] = mapped_column(
        ForeignKey("user_groups.id", ondelete="CASCADE"), nullable=False
    )
    group: Mapped["UserGroup"] = relationship(back_populates="users")

    profile: Mapped[Optional["UserProfile"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    activation_token: Mapped[Optional["ActivationToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    password_reset_token: Mapped[Optional["PasswordResetToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    cart: Mapped[Optional["Cart"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def password(self) -> None:
        raise AttributeError("Password is write-only")

    @password.setter
    def password(self, raw_password: str) -> None:
        self._hashed_password = hash_password(raw_password)

    def verify_password(self, raw_password: str) -> bool:
        return verify_password(raw_password, self._hashed_password)

    @validates("email")
    def validate_email(self, key, value):
        if "@" not in value:
            raise ValueError("Invalid email address")
        return value.lower()


class UserProfile(Base):
    __tablename__ = "user_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    gender: Mapped[Optional[GenderEnum]] = mapped_column(Enum(GenderEnum))
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date)
    avatar: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="profile")


class ActivationToken(TokenBase):
    __tablename__ = "activation_tokens"
    user: Mapped["User"] = relationship(back_populates="activation_token")


class PasswordResetToken(TokenBase):
    __tablename__ = "password_reset_tokens"
    user: Mapped["User"] = relationship(back_populates="password_reset_token")


class RefreshToken(TokenBase):
    __tablename__ = "refresh_tokens"
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc) + timedelta(days=30),
    )
    user: Mapped["User"] = relationship(back_populates="refresh_tokens")
