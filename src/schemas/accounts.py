from datetime import date

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from src.database.validators import accounts_validators
from src.database.models.accounts import UserGroupEnum, GenderEnum


class BaseEmailPasswordSchema(BaseModel):
    email: EmailStr
    password: str

    model_config = {"from_attributes": True}

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str):
        return accounts_validators.validate_email(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str):
        return accounts_validators.validate_password_strength(value)


class UserRegistrationRequestSchema(BaseEmailPasswordSchema):
    pass


class UserRegistrationResponseSchema(BaseModel):
    id: int
    email: EmailStr

    model_config = {"from_attributes": True}


class UserLoginRequestSchema(BaseEmailPasswordSchema):
    pass


class UserLoginResponseSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserActivationResendRequestSchema(BaseModel):
    email: EmailStr


class TokenRefreshRequestSchema(BaseModel):
    refresh_token: str


class TokenRefreshResponseSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserActivationRequestSchema(BaseModel):
    email: EmailStr
    token: str


class PasswordChangeRequestSchema(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str):
        return accounts_validators.validate_password_strength(value)


class PasswordResetRequestSchema(BaseModel):
    email: EmailStr


class PasswordResetCompleteRequestSchema(BaseEmailPasswordSchema):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str):
        return accounts_validators.validate_password_strength(value)


class UserProfileSchema(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[GenderEnum] = None
    avatar: Optional[str] = None
    info: Optional[str] = None
    date_of_birth: Optional[date] = None
    model_config = {"from_attributes": True}


class UserProfileUpdateSchema(BaseModel):
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    gender: Optional[GenderEnum] = None
    date_of_birth: Optional[date] = None
    avatar: Optional[str] = None
    info: Optional[str] = None

    model_config = {"from_attributes": True}


class MessageResponseSchema(BaseModel):
    message: str
