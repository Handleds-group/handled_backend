# app/auth.py
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserLogin, OTPVerify, TokenSchema, OTPRequest
from app.tokens import create_access_token, create_refresh_token
from app.email_utils import send_email
from app.dependencies import get_current_user
from passlib.hash import bcrypt
import random, string, datetime
from app.redis_client import redis_client

router = APIRouter()

def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

def save_otp_to_redis(email: str, otp_code: str, expire_seconds=600):
    redis_client.set(f"otp:{email}", otp_code, ex=expire_seconds)

def get_otp_from_redis(email: str):
    return redis_client.get(f"otp:{email}")

# --------------------------
# Signup
# --------------------------

@router.post("/signup", response_model=TokenSchema)
def signup(
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
    db: Session = Depends(get_db)
):
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    # Check existing user
    result = db.execute(select(User).where(User.email == email))
    existing_user = result.scalars().first()
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
    db.commit()
    db.refresh(new_user)

    # Generate OTP and send email
    otp_code = generate_otp()
    save_otp_to_redis(email, otp_code)
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
def verify_email(otp_data: OTPVerify, db: Session = Depends(get_db)):
    otp_saved = get_otp_from_redis(otp_data.email)
    if not otp_saved:
        raise HTTPException(status_code=400, detail="OTP expired or not found")
    if otp_saved != otp_data.otp_code:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    result = db.execute(select(User).where(User.email == otp_data.email))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_verified = True
    db.add(user)
    db.commit()

    # Delete OTP from Redis
    redis_client.delete(f"otp:{otp_data.email}")

    return {"message": "Email verified successfully"}

# --------------------------
# Login
# --------------------------

@router.post("/login", response_model=TokenSchema)
def login(user: UserLogin, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    result = db.execute(select(User).where(User.email == user.email))
    db_user = result.scalars().first()
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
def logout():
    # Optional: add token to Redis blocklist if using stateless JWT
    return {"message": "Logged out successfully"}

# --------------------------
# Forgot Password
# --------------------------

@router.post("/forgot-password")
def forgot_password(request: OTPRequest, background_tasks: BackgroundTasks):
    otp_code = generate_otp()
    save_otp_to_redis(request.email, otp_code)
    background_tasks.add_task(
        send_email,
        subject="Reset your Handled password",
        email_to=request.email,
        body=f"<h2 style='color:#A78BFA'>Your OTP for password reset: {otp_code}</h2>"
    )
    return {"message": "OTP sent to your email"}

@router.post("/reset-password")
def reset_password(
    otp_data: OTPVerify,
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    otp_saved = get_otp_from_redis(otp_data.email)
    if not otp_saved or otp_saved != otp_data.otp_code:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    result = db.execute(select(User).where(User.email == otp_data.email))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = bcrypt.hash(new_password)
    db.add(user)
    db.commit()
    redis_client.delete(f"otp:{otp_data.email}")

    return {"message": "Password reset successfully"}
