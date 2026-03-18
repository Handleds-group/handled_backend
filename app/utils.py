from fastapi import Request, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import jwt
import bcrypt
import hashlib
import json
import os
from typing import Optional, Dict, Any
from functools import wraps
import logging

from app.database import get_redis, get_db
from app import models

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

logger = logging.getLogger(__name__)

# Token functions
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def verify_token(token: str, token_type: str = "access"):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != token_type:
            return None
        return payload
    except jwt.PyJWTError:
        return None

async def get_current_user(token: str = Depends(OAuth2PasswordBearer(tokenUrl="/api/auth/login")), 
                          db: AsyncSession = Depends(get_db)):
    """Get current user from token"""
    
    # Check if token is blacklisted
    redis = await get_redis()
    is_blacklisted = await redis.get(f"blacklist:{token}")
    if is_blacklisted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked"
        )
    
    payload = await verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    result = await db.execute(
        select(models.User).where(models.User.email == email)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )
    
    return user

# Rate limiting decorator
def rate_limit(max_requests: int, window_seconds: int):
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            redis = await get_redis()
            
            # Get client IP
            client_ip = request.client.host
            endpoint = request.url.path
            
            # Create key
            key = f"rate_limit:{client_ip}:{endpoint}"
            
            # Get current count
            current = await redis.get(key)
            
            if current and int(current) >= max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later."
                )
            
            # Increment counter
            pipe = redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            await pipe.execute()
            
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator

# Idempotency decorator
def check_idempotency(timeout: int = 3600):
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            redis = await get_redis()
            
            # Get idempotency key from header
            idempotency_key = request.headers.get("Idempotency-Key")
            
            if not idempotency_key:
                # If no key, just execute (or you can require it)
                return await func(request, *args, **kwargs)
            
            # Check if we've seen this key before
            key = f"idempotency:{idempotency_key}"
            cached_response = await redis.get(key)
            
            if cached_response:
                # Return cached response
                return json.loads(cached_response)
            
            # Execute function
            response = await func(request, *args, **kwargs)
            
            # Cache response
            await redis.setex(
                key,
                timeout,
                json.dumps(response, default=str)
            )
            
            return response
        return wrapper
    return decorator

# Email sending function
async def send_email(to: str, subject: str, template: str, context: dict):
    """Send email using configured email service"""
    # Placeholder - implement with SendGrid, AWS SES, etc.
    logger.info(f"Sending email to {to}: {subject}")
    logger.info(f"Template: {template}, Context: {context}")
    
    # TODO: Implement actual email sending
    # Example with SendGrid:
    # import sendgrid
    # from sendgrid.helpers.mail import Mail
    # 
    # sg = sendgrid.SendGridAPIClient(api_key=os.getenv('SENDGRID_API_KEY'))
    # message = Mail(
    #     from_email='noreply@handled.app',
    #     to_emails=to,
    #     subject=subject,
    #     html_content=render_template(template, context)
    # )
    # sg.send(message)
    
    return True

# Login logging
async def log_login_attempt(
    db: AsyncSession,
    user_id: int,
    request: Request,
    success: bool,
    reason: Optional[str] = None
):
    """Log login attempt to database"""
    
    login_log = models.LoginHistory(
        user_id=user_id,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        success=success,
        failure_reason=reason
    )
    
    db.add(login_log)
    await db.commit()

# Invalidate user sessions
async def invalidate_user_sessions(user_id: int, redis):
    """Invalidate all sessions for a user"""
    # You could implement this by storing user's tokens in Redis
    # and clearing them, or using a version number in JWT
    await redis.set(f"user:invalidate:{user_id}", datetime.utcnow().timestamp())
    logger.info(f"Invalidated all sessions for user {user_id}")

# File upload to CDN
async def upload_to_cdn(file, folder: str = "uploads") -> str:
    """Upload file to CDN/storage"""
    # Placeholder - implement with Cloudinary, AWS S3, etc.
    # For now, return a mock URL
    import uuid
    file_ext = file.filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{file_ext}"
    
    # TODO: Upload to actual storage
    # Example with Cloudinary:
    # import cloudinary.uploader
    # result = cloudinary.uploader.upload(file.file, folder=folder)
    # return result['secure_url']
    
    return f"https://cdn.handled.app/{folder}/{filename}"

# Kill switch management
async def check_kill_switch():
    """Check if kill switch is active"""
    redis = await get_redis()
    return await redis.get("kill_switch:global") == "active"

async def activate_kill_switch(reason: str):
    """Activate global kill switch"""
    redis = await get_redis()
    await redis.setex("kill_switch:global", 3600, "active")
    await redis.set("kill_switch:reason", reason)
    logger.critical(f"🔴 KILL SWITCH ACTIVATED: {reason}")

async def deactivate_kill_switch():
    """Deactivate global kill switch"""
    redis = await get_redis()
    await redis.delete("kill_switch:global", "kill_switch:reason")
    logger.info("🟢 Kill switch deactivated")