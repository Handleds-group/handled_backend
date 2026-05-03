from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    age: Optional[int]
    occupation: Optional[str]
    gender: Optional[str]
    description: Optional[str]
    allergic: Optional[str]
    password: str


class SignupRequest(BaseModel):
    username: str
    email: EmailStr
    age: Optional[int]
    occupation: Optional[str]
    gender: Optional[str]
    description: Optional[str] = ""
    allergic: Optional[str]
    password: str
    confirm_password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    username: Optional[str]
    age: Optional[int]
    occupation: Optional[str]
    gender: Optional[str]
    description: Optional[str]
    allergic: Optional[str]


class UserProfileUpdate(BaseModel):
    username: Optional[str]
    email: Optional[EmailStr]
    allergic: Optional[str]
    description: Optional[str]


class UserProfileOut(BaseModel):
    username: Optional[str]
    email: Optional[EmailStr]
    allergic: Optional[str]
    description: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    age: Optional[int]
    occupation: Optional[str]
    gender: Optional[str]
    description: Optional[str]
    allergic: Optional[str]
    is_verified: bool
    is_premium: Optional[bool] = None
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class TokenSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class OTPRequest(BaseModel):
    email: EmailStr


class ChangePassword(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str


class DeleteAccountRequest(BaseModel):
    user_id: int


class BugReportCreate(BaseModel):
    name: Optional[str] = None
    error_message: str
    user_id: Optional[int] = None

    @field_validator("user_id", mode="before")
    @classmethod
    def normalize_user_id(cls, value):
        if value is None or value == "":
            return None
        user_id = int(value)
        return user_id if user_id > 0 else None


class BugReportOut(BaseModel):
    id: int
    name: Optional[str] = None
    error_message: str
    user_id: Optional[int] = None

    class Config:
        from_attributes = True


class PaymentCheckoutRequest(BaseModel):
    user_id: str
    plan: str
    email: Optional[EmailStr] = None


class PaymentCheckoutResponse(BaseModel):
    checkout_url: str


class DecisionRequest(BaseModel):
    user_id: str
    user_input: str = Field(..., min_length=1)
    tokens_used: int = 0


class DecisionResponseData(BaseModel):
    decision_id: str
    response: str
    cached: bool
    tier: str
    remaining_decisions_today: Optional[int] = None
    monthly_tokens_remaining: Optional[int] = None


class DecisionResponse(BaseModel):
    message: str
    data: DecisionResponseData
