from pydantic import BaseModel, EmailStr
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
    profile_pic: Optional[str]

class UserProfileOut(BaseModel):
    username: Optional[str]
    email: Optional[EmailStr]
    allergic: Optional[str]
    description: Optional[str]
    profile_pic: Optional[str]

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
    profile_pic: Optional[str]
    is_verified: bool

    class Config:
        from_attributes = True

class TokenSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class OTPRequest(BaseModel):
    email: EmailStr

class OTPVerify(BaseModel):
    email: EmailStr
    otp_code: Optional[str] = None

class ChangePassword(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str
