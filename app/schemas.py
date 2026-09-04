from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    is_ta: bool = False
    is_supervisor: bool = False


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    is_ta: bool
    is_supervisor: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RestoreRequest(BaseModel):
    email: EmailStr


class RestoreConfirm(BaseModel):
    email: EmailStr
    code: str
    new_password: str = Field(min_length=8)
