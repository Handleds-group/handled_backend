# app/auth.py
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Form
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.schemas import UserLogin, TokenSchema, OTPRequest, SignupRequest, RefreshTokenRequest
from app.tokens import create_access_token, create_refresh_token, decode_refresh_token
from app.email_utils import send_email, otp_email_html, welcome_email_html, login_alert_email_html
from app.dependencies import get_current_user
from passlib.hash import pbkdf2_sha256
from jose import ExpiredSignatureError, JWTError
import random, string, datetime
from app.redis_client import redis_client

router = APIRouter()

def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

def save_otp_to_redis(email: str, otp_code: str, expire_seconds=600):
    redis_client.set(f"otp:{email}", otp_code, ex=expire_seconds)
    redis_client.set(f"otp_code:{otp_code}", email, ex=expire_seconds)

def get_otp_from_redis(email: str):
    return redis_client.get(f"otp:{email}")


def get_email_from_otp(otp_code: str):
    return redis_client.get(f"otp_code:{otp_code}")


def delete_otp_from_redis(email: str, otp_code: str):
    redis_client.delete(f"otp:{email}")
    redis_client.delete(f"otp_code:{otp_code}")


def normalize_email(email: str) -> str:
    return email.strip().lower()

# --------------------------
# Signup
# --------------------------

@router.post("/signup", response_model=TokenSchema)
def signup(
    payload: SignupRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    email = normalize_email(payload.email)
    if payload.password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    # Check existing user
    result = db.execute(select(User).where(User.email == email))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Save user (hashed password)
    hashed_pw = pbkdf2_sha256.hash(payload.password)
    new_user = User(
        username=payload.username,
        email=email,
        age=payload.age,
        occupation=payload.occupation,
        gender=payload.gender,
        description=payload.description,
        allergic=payload.allergic,
        password_hash=hashed_pw,
        is_verified=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Send welcome email
    background_tasks.add_task(
        send_email,
        subject="Welcome to Handled",
        email_to=email,
        body=welcome_email_html(payload.username)
    )

    return {
        "access_token": create_access_token({"user_id": new_user.id}),
        "refresh_token": create_refresh_token({"user_id": new_user.id}),
        "token_type": "bearer",
    }

# --------------------------
# Login
# --------------------------

@router.post("/login", response_model=TokenSchema)
def login(user: UserLogin, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    email = normalize_email(user.email)
    result = db.execute(select(User).where(User.email == email))
    db_user = result.scalars().first()
    if not db_user or not pbkdf2_sha256.verify(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Send login warning email
    login_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    background_tasks.add_task(
        send_email,
        subject="New login detected",
        email_to=email,
        body=login_alert_email_html(login_time_utc=login_time)
    )

    return {
        "access_token": create_access_token({"user_id": db_user.id}),
        "refresh_token": create_refresh_token({"user_id": db_user.id}),
        "token_type": "bearer",
    }

@router.post("/refresh", response_model=TokenSchema)
def refresh_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        token_payload = decode_refresh_token(payload.refresh_token)
        user_id = token_payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.execute(select(User).where(User.id == user_id)).scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "access_token": create_access_token({"user_id": user.id}),
        "refresh_token": create_refresh_token({"user_id": user.id}),
        "token_type": "bearer",
    }


@router.post("/logout")
def logout():
    # Optional: add token to Redis blocklist if using stateless JWT
    return {"message": "Logged out successfully"}

# --------------------------
# Forgot Password
# --------------------------

@router.post("/forgot-password")
def forgot_password(request: OTPRequest, background_tasks: BackgroundTasks):
    request.email = normalize_email(request.email)
    otp_code = generate_otp()
    save_otp_to_redis(request.email, otp_code)
    background_tasks.add_task(
        send_email,
        subject="Reset your Handled password",
        email_to=request.email,
        body=otp_email_html(
            title="Reset your Handled password",
            otp_code=otp_code,
            purpose="Password reset"
        )
    )
    return {"message": "OTP sent to your email"}

@router.post("/reset-password")
def reset_password(
    otp_code: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    if not otp_code or not new_password or not confirm_password:
        raise HTTPException(status_code=422, detail="otp_code, new_password and confirm_password are required")

    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")

    email = get_email_from_otp(otp_code)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    result = db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = pbkdf2_sha256.hash(new_password)
    db.add(user)
    db.commit()
    delete_otp_from_redis(email, otp_code)

    return {"message": "Password reset successfully"}
