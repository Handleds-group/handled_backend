from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timedelta
import random
import string
import bcrypt
from typing import Optional

from database import get_db, get_redis
import schemas, models
from utils import (
    create_access_token, create_refresh_token, 
    verify_token, get_current_user, send_email,
    check_idempotency, rate_limit, log_login_attempt,
    invalidate_user_sessions
)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

@router.post("/signup/step1", response_model=dict)
@rate_limit(max_requests=5, window_seconds=3600)  # 5 per hour
@check_idempotency(timeout=3600)
async def signup_step1(
    request: Request,
    user_data: schemas.UserOnboardingStep1,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """First step: Check email/username availability"""
    
    # Check if email exists
    result = await db.execute(
        select(models.User).where(models.User.email == user_data.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if username exists
    result = await db.execute(
        select(models.User).where(models.User.username == user_data.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Store in Redis with TTL (30 minutes)
    redis = await get_redis()
    key = f"signup:step1:{user_data.email}"
    await redis.setex(
        key,
        1800,  # 30 minutes
        user_data.model_dump_json()
    )
    
    return {
        "message": "Email and username available",
        "next_step": "/api/auth/signup/step2"
    }

@router.post("/signup/step2", response_model=dict)
@rate_limit(max_requests=10, window_seconds=3600)
@check_idempotency(timeout=3600)
async def signup_step2(
    request: Request,
    profile_data: schemas.UserOnboardingStep2,
    email: str,  # Pass email from frontend
    db: AsyncSession = Depends(get_db)
):
    """Second step: Save profile information"""
    
    redis = await get_redis()
    
    # Check if step1 completed
    step1_key = f"signup:step1:{email}"
    step1_data = await redis.get(step1_key)
    if not step1_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please complete step 1 first"
        )
    
    # Store step2 data
    key = f"signup:step2:{email}"
    await redis.setex(
        key,
        1800,  # 30 minutes
        profile_data.model_dump_json()
    )
    
    return {
        "message": "Profile information saved",
        "next_step": "/api/auth/signup/step3"
    }

@router.post("/signup/step3", response_model=dict)
@rate_limit(max_requests=10, window_seconds=3600)
@check_idempotency(timeout=3600)
async def signup_step3(
    request: Request,
    password_data: schemas.UserOnboardingStep3,
    email: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Third step: Set password and upload profile pic placeholder"""
    
    redis = await get_redis()
    
    # Check if step2 completed
    step2_key = f"signup:step2:{email}"
    step2_data = await redis.get(step2_key)
    if not step2_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please complete step 2 first"
        )
    
    # Hash password
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_data.password.encode('utf-8'), salt)
    
    # Store in Redis with shorter TTL (15 minutes for final step)
    key = f"signup:complete:{email}"
    await redis.setex(
        key,
        900,  # 15 minutes
        hashed_password.decode('utf-8')
    )
    
    # Generate and send OTP
    otp = ''.join(random.choices(string.digits, k=6))
    otp_expiry = datetime.utcnow() + timedelta(minutes=10)
    
    # Store OTP in database
    db_otp = models.OTP(
        email=email,
        otp=otp,
        expires_at=otp_expiry
    )
    db.add(db_otp)
    await db.commit()
    
    # Send email in background
    background_tasks.add_task(
        send_email,
        to=email,
        subject="Verify your email for Handled",
        template="otp_verification",
        context={"otp": otp, "expiry_minutes": 10}
    )
    
    return {
        "message": "Password set. Please verify your email.",
        "next_step": "/api/auth/signup/verify"
    }

@router.post("/signup/verify", response_model=schemas.TokenResponse)
@rate_limit(max_requests=5, window_seconds=300)  # 5 per 5 minutes
@check_idempotency(timeout=300)
async def signup_verify(
    request: Request,
    verification: schemas.UserOnboardingComplete,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Final step: Verify OTP and create user"""
    
    redis = await get_redis()
    
    # Check if all steps completed
    step1_key = f"signup:step1:{verification.email}"
    step2_key = f"signup:step2:{verification.email}"
    password_key = f"signup:complete:{verification.email}"
    
    step1_data = await redis.get(step1_key)
    step2_data = await redis.get(step2_key)
    hashed_password = await redis.get(password_key)
    
    if not all([step1_data, step2_data, hashed_password]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please complete all signup steps"
        )
    
    # Verify OTP
    result = await db.execute(
        select(models.OTP).where(
            models.OTP.email == verification.email,
            models.OTP.otp == verification.otp,
            models.OTP.is_used == False,
            models.OTP.expires_at > datetime.utcnow()
        ).order_by(models.OTP.created_at.desc())
    )
    db_otp = result.scalar_one_or_none()
    
    if not db_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )
    
    # Mark OTP as used
    db_otp.is_used = True
    
    # Parse stored data
    import json
    step1 = json.loads(step1_data)
    step2 = json.loads(step2_data)
    
    # Create user
    new_user = models.User(
        email=step1["email"],
        username=step1["username"],
        hashed_password=hashed_password,
        age=step2.get("age"),
        occupation=step2.get("occupation"),
        gender=step2.get("gender"),
        bio=step2.get("bio"),
        allergies=step2.get("allergies"),
        is_verified=True,
        verified_at=datetime.utcnow()
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Clean up Redis
    await redis.delete(step1_key, step2_key, password_key)
    
    # Generate tokens
    access_token = create_access_token({"sub": new_user.email})
    refresh_token = create_refresh_token({"sub": new_user.email})
    
    # Save refresh token
    new_user.refresh_token = refresh_token
    await db.commit()
    
    # Log login
    await log_login_attempt(
        db=db,
        user_id=new_user.id,
        request=request,
        success=True
    )
    
    # Send welcome email
    background_tasks.add_task(
        send_email,
        to=new_user.email,
        subject="Welcome to Handled!",
        template="welcome",
        context={"username": new_user.username}
    )
    
    return schemas.TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )

@router.post("/login", response_model=schemas.TokenResponse)
@rate_limit(max_requests=5, window_seconds=300)  # 5 per 5 minutes
@check_idempotency(timeout=60)
async def login(
    request: Request,
    credentials: schemas.UserLogin,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Login user and send warning email"""
    
    # Get user
    result = await db.execute(
        select(models.User).where(models.User.email == credentials.email)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        # Fake password check to prevent timing attacks
        bcrypt.checkpw(b"fake", b"fake")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check if account is locked
    if user.failed_login_attempts >= 5:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account locked. Too many failed attempts. Try again in 30 minutes."
        )
    
    # Verify password
    if not bcrypt.checkpw(
        credentials.password.encode('utf-8'),
        user.hashed_password.encode('utf-8')
    ):
        # Increment failed attempts
        user.failed_login_attempts += 1
        await db.commit()
        
        # Log failed attempt
        await log_login_attempt(
            db=db,
            user_id=user.id,
            request=request,
            success=False,
            reason="Invalid password"
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Reset failed attempts
    user.failed_login_attempts = 0
    user.last_login_at = datetime.utcnow()
    user.last_login_ip = request.client.host
    
    # Generate new tokens
    access_token = create_access_token({"sub": user.email})
    refresh_token = create_refresh_token({"sub": user.email})
    user.refresh_token = refresh_token
    
    await db.commit()
    
    # Log successful login
    await log_login_attempt(
        db=db,
        user_id=user.id,
        request=request,
        success=True
    )
    
    # Send warning email in background
    background_tasks.add_task(
        send_email,
        to=user.email,
        subject="New login to your Handled account",
        template="login_alert",
        context={
            "username": user.username,
            "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "ip": request.client.host,
            "user_agent": request.headers.get("user-agent", "Unknown")
        }
    )
    
    return schemas.TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )

@router.post("/logout")
@rate_limit(max_requests=10, window_seconds=60)
async def logout(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    """Logout user and invalidate tokens"""
    
    # Get current user
    user = await get_current_user(token, db)
    
    # Clear refresh token
    user.refresh_token = None
    await db.commit()
    
    # Add token to blacklist (until expiry)
    payload = await verify_token(token)
    if payload:
        exp = payload.get("exp")
        if exp:
            ttl = exp - datetime.utcnow().timestamp()
            if ttl > 0:
                await redis.setex(f"blacklist:{token}", int(ttl), "revoked")
    
    # Invalidate all sessions (optional)
    await invalidate_user_sessions(user.id, redis)
    
    return {"message": "Successfully logged out"}

@router.post("/refresh", response_model=schemas.TokenResponse)
@rate_limit(max_requests=10, window_seconds=3600)
async def refresh_token(
    refresh_data: schemas.RefreshToken,
    db: AsyncSession = Depends(get_db)
):
    """Get new access token using refresh token"""
    
    # Verify refresh token
    payload = await verify_token(refresh_data.refresh_token, token_type="refresh")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    email = payload.get("sub")
    
    # Get user
    result = await db.execute(
        select(models.User).where(
            models.User.email == email,
            models.User.refresh_token == refresh_data.refresh_token
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Generate new tokens
    new_access_token = create_access_token({"sub": email})
    new_refresh_token = create_refresh_token({"sub": email})
    
    # Update refresh token
    user.refresh_token = new_refresh_token
    await db.commit()
    
    return schemas.TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token
    )

@router.post("/resend-otp")
@rate_limit(max_requests=3, window_seconds=3600)
async def resend_otp(
    request: schemas.OTPRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Resend OTP for email verification"""
    
    # Check if user exists and not verified
    result = await db.execute(
        select(models.User).where(models.User.email == request.email)
    )
    user = result.scalar_one_or_none()
    
    if user and user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified"
        )
    
    # Generate new OTP
    otp = ''.join(random.choices(string.digits, k=6))
    otp_expiry = datetime.utcnow() + timedelta(minutes=10)
    
    # Invalidate old OTPs
    await db.execute(
        update(models.OTP)
        .where(
            models.OTP.email == request.email,
            models.OTP.is_used == False
        )
        .values(is_used=True)
    )
    
    # Store new OTP
    db_otp = models.OTP(
        email=request.email,
        otp=otp,
        expires_at=otp_expiry
    )
    db.add(db_otp)
    await db.commit()
    
    # Send email
    background_tasks.add_task(
        send_email,
        to=request.email,
        subject="Your Handled verification code",
        template="otp_verification",
        context={"otp": otp, "expiry_minutes": 10}
    )
    
    return {"message": "OTP resent successfully"}