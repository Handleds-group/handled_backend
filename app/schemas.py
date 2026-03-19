from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime
import re

# User schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    
    @validator('password')
    def validate_password(cls, v):
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one number')
        return v

# Onboarding schemas
class UserOnboardingStep1(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)

class UserOnboardingStep2(BaseModel):
    age: int = Field(..., ge=13, le=120)
    occupation: str = Field(..., max_length=100)
    gender: str = Field(..., max_length=50)
    bio: Optional[str] = Field(None, max_length=500)
    allergies: Optional[str] = Field(None, max_length=500)

class UserOnboardingStep3(BaseModel):
    password: str = Field(..., min_length=8)
    confirm_password: str
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v

class UserOnboardingComplete(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)

# Profile schemas
class UserProfile(BaseModel):
    email: EmailStr
    username: str
    age: Optional[int] = None
    occupation: Optional[str] = None
    gender: Optional[str] = None
    bio: Optional[str] = None
    allergies: Optional[str] = None
    profile_pic: Optional[str] = None
    is_verified: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserProfileUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    age: Optional[int] = Field(None, ge=13, le=120)
    occupation: Optional[str] = Field(None, max_length=100)
    gender: Optional[str] = Field(None, max_length=50)
    bio: Optional[str] = Field(None, max_length=500)
    allergies: Optional[str] = Field(None, max_length=500)
    profile_pic: Optional[str] = None

# Auth schemas
class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # 15 minutes

class RefreshToken(BaseModel):
    refresh_token: str

class OTPVerify(BaseModel):
    email: EmailStr
    otp: str

class OTPRequest(BaseModel):
    email: EmailStr

class LoginHistoryResponse(BaseModel):
    ip_address: str
    user_agent: Optional[str]
    login_at: datetime
    success: bool
    
    class Config:
        from_attributes = True


# Add these schemas to your existing schemas.py

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordVerify(BaseModel):
    email: EmailStr
    otp: str
    new_password: str = Field(..., min_length=8)
    confirm_password: str
    
    @validator('new_password')
    def validate_password(cls, v):
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one number')
        return v
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)
    confirm_password: str
    
    @validator('new_password')
    def validate_password(cls, v):
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one number')
        return v
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v

class PasswordResetResponse(BaseModel):
    message: str