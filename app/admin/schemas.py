from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class AdminLoginRequest(BaseModel):
    password: str

class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class AdminUserListOut(BaseModel):
    id: int
    username: Optional[str]
    email: Optional[EmailStr]
    is_premium: Optional[bool]
    created_at: Optional[datetime]
    last_seen: Optional[datetime]

    class Config:
        from_attributes = True

class PaymentTransactionOut(BaseModel):
    id: int
    amount: int
    currency: str
    status: str
    plan: Optional[str]
    reference: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True

class BugReportAdminOut(BaseModel):
    id: int
    user_id: Optional[int]
    name: Optional[str]
    error_message: str
    created_at: Optional[datetime]

    class Config:
        from_attributes = True

class AdminUserProfileOut(BaseModel):
    id: int
    username: Optional[str]
    email: Optional[EmailStr]
    description: Optional[str]
    created_at: Optional[datetime]
    last_seen: Optional[datetime]
    is_premium: Optional[bool]
    tokens_used: Optional[int]
    last_premium_transactions: List[PaymentTransactionOut] = []

    class Config:
        from_attributes = True

class NotificationCreate(BaseModel):
    user_id: int
    title: str
    message: str

class BroadcastNotificationCreate(BaseModel):
    title: str
    message: str
    send_email: bool = True

class BroadcastNotificationResponse(BaseModel):
    success: bool
    message: str
    recipients_count: int
    failed_count: int

class NotificationOut(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    is_read: bool
    created_at: Optional[datetime]

    class Config:
        from_attributes = True

class PaymentSummaryByCurrency(BaseModel):
    currency: str
    total_amount: int
    total_count: int

class WalletOut(BaseModel):
    id: int
    balance: int
    currency: str

    class Config:
        from_attributes = True

class WithdrawalCreate(BaseModel):
    amount: int
    currency: Optional[str] = None
    destination: str

class WithdrawalOut(BaseModel):
    id: int
    amount: int
    currency: str
    destination: str
    status: str
    created_at: Optional[datetime]
    processed_at: Optional[datetime]

    class Config:
        from_attributes = True
