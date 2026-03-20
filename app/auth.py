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
from passlib.hash import pbkdf2_sha256
import random, string, datetime
from app.redis_client import redis_client

router = APIRouter()

def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

def build_otp_email_html(
    title: str,
    otp_code: str,
    subtitle: str = "Use the code below to continue",
    purpose: str | None = None,
) -> str:
    # Clean, detailed, darker-purple email template
    return f"""
    <div style="font-family: Arial, sans-serif; background:#f2ecff; padding:24px;">
      <div style="max-width:560px; margin:0 auto; background:#ffffff; border-radius:16px; border:1px solid #decff8; overflow:hidden;">
        <div style="background:#e9ddff; padding:18px 22px;">
          <h2 style="margin:0; color:#5b2aa8; font-weight:700;">{title}</h2>
        </div>
        <div style="padding:22px;">
          <p style="margin:0 0 12px 0; color:#4a3b73; font-size:14px;">{subtitle}</p>
          {f'<div style="margin:0 0 12px 0; color:#5b2aa8; font-size:12px; font-weight:700;">{purpose}</div>' if purpose else ''}
          <div style="text-align:center; margin:18px 0;">
            <span style="display:inline-block; background:#efe3ff; color:#5b2aa8; padding:12px 20px; border-radius:10px; font-size:24px; letter-spacing:3px; font-weight:700;">
              {otp_code}
            </span>
          </div>
          <div style="background:#f7f3ff; border:1px dashed #d8c6f7; padding:12px; border-radius:10px; color:#5a4a7a; font-size:12px;">
            <div style="font-weight:700; color:#5b2aa8; margin-bottom:6px;">OTP Details</div>
            <div>Length: 6 digits</div>
            <div>Expires in: 10 minutes</div>
            <div>One-time use only</div>
          </div>
          <p style="margin:12px 0 0 0; color:#6b5a8a; font-size:12px;">If you did not request this, you can safely ignore this email.</p>
        </div>
      </div>
      <p style="max-width:560px; margin:10px auto 0; color:#7e6aa8; font-size:11px; text-align:center;">
        Handled • Secure Verification
      </p>
    </div>
    """

def save_otp_to_redis(email: str, otp_code: str, expire_seconds=600):
    redis_client.set(f"otp:{email}", otp_code, ex=expire_seconds)

def get_otp_from_redis(email: str):
    return redis_client.get(f"otp:{email}")

def normalize_email(email: str) -> str:
    return email.strip().lower()

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
    email = normalize_email(email)
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    # Check existing user
    result = db.execute(select(User).where(User.email == email))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Save user (hashed password)
    hashed_pw = pbkdf2_sha256.hash(password)
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
        body=build_otp_email_html(
            title="Verify your Handled account",
            otp_code=otp_code,
            subtitle="Thanks for signing up. Use the code below to verify your email address.",
            purpose="Email verification"
        )
    )

    return {
        "access_token": create_access_token({"user_id": new_user.id}),
        "refresh_token": create_refresh_token({"user_id": new_user.id})
    }

# --------------------------
# Verify Email OTP
# --------------------------

@router.post("/verify-email")
def verify_email(otp_data: OTPVerify, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    otp_data.email = normalize_email(otp_data.email)
    # If no otp_code provided, send a new OTP
    if not otp_data.otp_code:
        otp_code = generate_otp()
        save_otp_to_redis(otp_data.email, otp_code)
        background_tasks.add_task(
            send_email,
            subject="Your Handled verification code",
            email_to=otp_data.email,
            body=build_otp_email_html(
                title="Email verification code",
                otp_code=otp_code,
                subtitle="Use this code to verify your email address.",
                purpose="Email verification"
            )
        )
        return {"message": "Verification OTP sent"}

    otp_saved = get_otp_from_redis(otp_data.email)
    if not otp_saved:
        raise HTTPException(status_code=400, detail="OTP expired or not found")
    if otp_saved != otp_data.otp_code:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    result = db.execute(select(User).where(User.email == otp_data.email))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Please sign up first.")

    user.is_verified = True
    db.add(user)
    db.commit()

    # Delete OTP from Redis
    redis_client.delete(f"otp:{otp_data.email}")

    return {"message": "Email verified successfully"}

# --------------------------
# Resend Verify Email OTP
# --------------------------

@router.post("/verify-email/send")
def send_verify_email_otp(request: OTPRequest, background_tasks: BackgroundTasks):
    request.email = normalize_email(request.email)
    otp_code = generate_otp()
    save_otp_to_redis(request.email, otp_code)
    background_tasks.add_task(
        send_email,
        subject="Your Handled verification code",
        email_to=request.email,
        body=build_otp_email_html(
            title="Email verification code",
            otp_code=otp_code,
            subtitle="Use this code to verify your email address.",
            purpose="Email verification"
        )
    )
    return {"message": "Verification OTP sent"}

# --------------------------
# Login
# --------------------------

@router.post("/login", response_model=TokenSchema)
def login(user: UserLogin, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    result = db.execute(select(User).where(User.email == user.email))
    db_user = result.scalars().first()
    if not db_user or not pbkdf2_sha256.verify(user.password, db_user.password_hash):
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
        body=build_otp_email_html(
            title="Reset your Handled password",
            otp_code=otp_code,
            subtitle="We received a request to reset your password. Use the code below to continue.",
            purpose="Password reset"
        )
    )
    return {"message": "OTP sent to your email"}

@router.post("/reset-password")
def reset_password(
    otp_data: OTPVerify,
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    otp_data.email = normalize_email(otp_data.email)
    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    otp_saved = get_otp_from_redis(otp_data.email)
    if not otp_saved or otp_saved != otp_data.otp_code:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    result = db.execute(select(User).where(User.email == otp_data.email))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = pbkdf2_sha256.hash(new_password)
    db.add(user)
    db.commit()
    redis_client.delete(f"otp:{otp_data.email}")

    return {"message": "Password reset successfully"}
