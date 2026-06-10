"""API request/response schemas (pydantic)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=512)  # quality checked in passwords.py


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class VerifyEmailIn(BaseModel):
    token: str = Field(min_length=16, max_length=128)


class StepUpIn(BaseModel):
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    email_verified: bool
    created_at: datetime


class StepUpOut(BaseModel):
    step_up_token: str
    expires_in_minutes: int


class MessageOut(BaseModel):
    message: str
