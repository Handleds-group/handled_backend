from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    age = Column(Integer, nullable=True)
    occupation = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    description = Column(String, nullable=True)
    allergic = Column(String, nullable=True)
    profile_pic = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class OTP(Base):
    __tablename__ = "otp"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    code = Column(String, nullable=False)
    type = Column(String, nullable=False)  # signup / forgot_password
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
