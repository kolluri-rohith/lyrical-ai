from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.schemas.base import CamelModel


class RegisterRequest(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be empty")
        return value


class LoginRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(CamelModel):
    id: int
    name: str
    email: str
    created_at: datetime


class TokenResponse(CamelModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
