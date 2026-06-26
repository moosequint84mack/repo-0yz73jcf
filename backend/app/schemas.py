"""Pydantic request/response schemas for auth, admin, and chat APIs."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    display_name: str
    role: str
    is_active: bool
    created_at: dt.datetime
    last_login_at: dt.datetime | None = None


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class AdminCreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=120)
    role: str = Field(default="user", pattern="^(user|superuser)$")
    is_active: bool = True


class AdminUpdateUserRequest(BaseModel):
    is_active: bool | None = None
    role: str | None = Field(default=None, pattern="^(user|superuser)$")
    display_name: str | None = Field(default=None, max_length=120)
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sender_id: int
    recipient_id: int
    body: str
    created_at: dt.datetime
    read_at: dt.datetime | None = None


class SendMessageRequest(BaseModel):
    recipient_id: int
    body: str = Field(min_length=1, max_length=4000)


class ConversationPreview(BaseModel):
    user: UserOut
    last_message: ChatMessageOut | None = None
    unread: int = 0
