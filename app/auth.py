# app/auth.py
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserLogin, OTPVerify, TokenSchema, OTPRequest
from app.tokens import create_access_token, create_refresh_token
from app.email_utils import send_email
from app.dependencies import get_current_user
from passlib.hash import bcrypt
import random, string, datetime
import redis.asyncio as redis
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

# --------------------------
# Redis setup (modern)
# --------------------------
REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    raise RuntimeError("REDIS_URL is not set in environment")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)



def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

async def save_otp_to_redis(email: str, otp_code: str, expire_seconds=600):
    await redis_client.set(f"otp:{email}", otp_code, ex=expire_seconds)

async def get_otp_from_redis(email: str):
    return await redis_client.get(f"otp:{email}")

# --------------------------
# Signup
# --------------------------

@router.post("/signup", response_model=TokenSchema)
async def signup(
    background_tasks: BackgroundTasks,
    username: str = Form(...),
    email: str = Form(...),
    age: int = Form(...),
    occupation: str = Form(...),
    gender: str = Form(...),
    description: str = Form(...),
    allergic: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    profile_pic: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    # Check existing user
    result = await db.execute(User.__table__.select().where(User.email == email))
    existing_user = result.scalar()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Save user (hashed password)
    hashed_pw = bcrypt.hash(password)
    new_user = User(
        username=username,
        email=email,
        age=age,
        occupation=occupation,
        gender=gender,
        description=description,
        allergic=allergic,
        profile_pic=profile_pic.filename,  # store filename
        password_hash=hashed_pw,
        is_verified=False
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # Generate OTP and send email
    otp_code = generate_otp()
    await save_otp_to_redis(email, otp_code)
    background_tasks.add_task(
        send_email,
        subject="Verify your Handled account",
        email_to=email,
        body=f"<h2 style='color:#A78BFA'>Your OTP: {otp_code}</h2><p>Use this to verify your email</p>"
    )

    return {
        "access_token": create_access_token({"user_id": new_user.id}),
        "refresh_token": create_refresh_token({"user_id": new_user.id})
    }

# --------------------------
# Verify Email OTP
# --------------------------

@router.post("/verify-email")
async def verify_email(otp_data: OTPVerify, db: AsyncSession = Depends(get_db)):
    otp_saved = await get_otp_from_redis(otp_data.email)
    if not otp_saved:
        raise HTTPException(status_code=400, detail="OTP expired or not found")
    if otp_saved != otp_data.otp_code:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    result = await db.execute(User.__table__.select().where(User.email == otp_data.email))
    user = result.scalar()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_verified = True
    db.add(user)
    await db.commit()

    # Delete OTP from Redis
    await redis_client.delete(f"otp:{otp_data.email}")

    return {"message": "Email verified successfully"}

# --------------------------
# Login
# --------------------------

@router.post("/login", response_model=TokenSchema)
async def login(user: UserLogin, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    result = await db.execute(User.__table__.select().where(User.email == user.email))
    db_user = result.scalar()
    if not db_user or not bcrypt.verify(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Send login warning email
    background_tasks.add_task(
        send_email,
        subject="New login to your Handled account",
        email_to=user.email,
        body=f"<p>Your account was logged in on {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>"
    )

    return {
        "access_token": create_access_token({"user_id": db_user.id}),
        "refresh_token": create_refresh_token({"user_id": db_user.id})
    }

# --------------------------
# Logout
# --------------------------

@router.post("/logout")
async def logout():
    # Optional: add token to Redis blocklist if using stateless JWT
    return {"message": "Logged out successfully"}

# --------------------------
# Forgot Password
# --------------------------

@router.post("/forgot-password")
async def forgot_password(request: OTPRequest, background_tasks: BackgroundTasks):
    otp_code = generate_otp()
    await save_otp_to_redis(request.email, otp_code)
    background_tasks.add_task(
        send_email,
        subject="Reset your Handled password",
        email_to=request.email,
        body=f"<h2 style='color:#A78BFA'>Your OTP for password reset: {otp_code}</h2>"
    )
    return {"message": "OTP sent to your email"}

@router.post("/reset-password")
async def reset_password(
    otp_data: OTPVerify,
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    otp_saved = await get_otp_from_redis(otp_data.email)
    if not otp_saved or otp_saved != otp_data.otp_code:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    result = await db.execute(User.__table__.select().where(User.email == otp_data.email))
    user = result.scalar()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = bcrypt.hash(new_password)
    db.add(user)
    await db.commit()
    await redis_client.delete(f"otp:{otp_data.email}")

    return {"message": "Password reset successfully"}
