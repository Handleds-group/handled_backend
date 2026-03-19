from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Enum, Float
from sqlalchemy.sql import func
import enum
from database import Base

class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"
    PREMIUM = "premium"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    # Profile information
    age = Column(Integer, nullable=True)
    occupation = Column(String(100), nullable=True)
    gender = Column(String(50), nullable=True)
    bio = Column(Text, nullable=True)  # description about you
    allergies = Column(Text, nullable=True)  # what are you allergic to
    profile_pic = Column(String(500), nullable=True)  # URL to profile picture
    
    # Account status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    role = Column(Enum(UserRole), default=UserRole.USER)
    
    # Tokens and security
    refresh_token = Column(String(500), nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_login_ip = Column(String(50), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    verified_at = Column(DateTime(timezone=True), nullable=True)

class OTP(Base):
    __tablename__ = "otps"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), index=True, nullable=False)
    otp = Column(String(6), nullable=False)
    purpose = Column(String(50), default="email_verification")  # email_verification, password_reset
    is_used = Column(Boolean, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class LoginHistory(Base):
    __tablename__ = "login_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    ip_address = Column(String(50))
    user_agent = Column(Text)
    location = Column(String(255), nullable=True)  # Could be derived from IP
    login_at = Column(DateTime(timezone=True), server_default=func.now())
    success = Column(Boolean, default=True)
    failure_reason = Column(String(255), nullable=True)