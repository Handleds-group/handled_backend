# utils.py - Shared utilities (auth, rate limiting, idempotency, email)

import json
import os
import logging
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Callable, Any, Awaitable

from fastapi import HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import models
from database import get_redis

# Optional dependency: PyJWT
try:
    import jwt
except Exception:  # pragma: no cover - handled at runtime
    jwt = None

logger = logging.getLogger(__name__)

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

async def send_email(
    to: str, 
    subject: str, 
    template: str, 
    context: dict,
    provider: Optional[str] = None
) -> bool:
    """Send email using configured provider"""
    
    provider = provider or os.getenv("EMAIL_PROVIDER", "gmail")
    
    try:
        if provider == "gmail":
            return await _send_via_gmail(to, subject, template, context)
        elif provider == "sendgrid":
            return await _send_via_sendgrid(to, subject, template, context)
        elif provider == "ses":
            return await _send_via_ses(to, subject, template, context)
        elif provider == "resend":
            return await _send_via_resend(to, subject, template, context)
        else:
            # Default to SMTP
            return await _send_via_smtp(to, subject, template, context)
            
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {str(e)}")
        
        # Queue for retry if enabled
        if os.getenv("EMAIL_QUEUE_ENABLED") == "True":
            await _queue_email_for_retry(to, subject, template, context)
        
        return False

# -------------------------------------------------------------------
# Auth helpers (JWT)
# -------------------------------------------------------------------

def _require_jwt():
    if jwt is None:
        raise RuntimeError(
            "PyJWT is not installed. Run `pip install PyJWT` to enable JWT features."
        )

def create_access_token(data: dict) -> str:
    _require_jwt()
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=ACCESS_EXPIRE_MINUTES)
    to_encode["type"] = "access"
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict) -> str:
    _require_jwt()
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(days=REFRESH_EXPIRE_DAYS)
    to_encode["type"] = "refresh"
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def verify_token(token: str, token_type: str = "access") -> Optional[dict]:
    _require_jwt()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if token_type and payload.get("type") != token_type:
            return None
        return payload
    except Exception:
        return None

async def get_current_user(token: str, db: AsyncSession):
    payload = await verify_token(token, token_type="access")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    result = await db.execute(select(models.User).where(models.User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    return user

# -------------------------------------------------------------------
# Rate limiting & idempotency
# -------------------------------------------------------------------

def rate_limit(max_requests: int, window_seconds: int):
    def decorator(func: Callable[..., Awaitable[Any]]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request = kwargs.get("request")
            if request is None:
                # If request isn't available, just proceed
                return await func(*args, **kwargs)

            redis = await get_redis()
            key = f"rate:{request.client.host}:{request.url.path}"
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, window_seconds)
            if count > max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded"
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def check_idempotency(timeout: int = 300):
    def decorator(func: Callable[..., Awaitable[Any]]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request = kwargs.get("request")
            if request is None:
                return await func(*args, **kwargs)

            key = request.headers.get("Idempotency-Key")
            if not key:
                return await func(*args, **kwargs)

            redis = await get_redis()
            redis_key = f"idem:{key}"
            exists = await redis.exists(redis_key)
            if exists:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Duplicate request"
                )

            await redis.setex(redis_key, timeout, "1")
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# -------------------------------------------------------------------
# Login history & session invalidation
# -------------------------------------------------------------------

async def log_login_attempt(
    db: AsyncSession,
    user_id: int,
    request: Request,
    success: bool,
    reason: Optional[str] = None
):
    entry = models.LoginHistory(
        user_id=user_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        success=success,
        failure_reason=reason
    )
    db.add(entry)
    await db.commit()

async def invalidate_user_sessions(user_id: int, redis=None):
    redis = redis or await get_redis()
    await redis.delete(f"sessions:{user_id}")

# -------------------------------------------------------------------
# Uploads (placeholder)
# -------------------------------------------------------------------

async def upload_to_cdn(file, folder: str = "uploads") -> str:
    os.makedirs(folder, exist_ok=True)
    file_path = os.path.join(folder, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())
    return f"/{folder}/{file.filename}"

# -------------------------------------------------------------------
# Kill switch (placeholder hook)
# -------------------------------------------------------------------

def kill_switch() -> bool:
    return os.getenv("MAINTENANCE_MODE", "False") == "True"

async def _send_via_gmail(to: str, subject: str, template: str, context: dict) -> bool:
    """Send via Gmail SMTP with app password"""
    
    gmail_user = os.getenv("GMAIL_ADDRESS")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD").replace(" ", "")  # Remove spaces
    
    if not gmail_user or not gmail_password:
        raise ValueError("Gmail credentials not configured")
    
    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{os.getenv('SMTP_FROM_NAME', 'Handled')} <{gmail_user}>"
    msg['To'] = to
    
    # Create HTML content
    html_content = await _render_template(template, context)
    
    # Attach HTML
    msg.attach(MIMEText(html_content, 'html'))
    
    # Send via SMTP
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gmail_user, gmail_password)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Email sent to {to} via Gmail")
        return True
        
    except Exception as e:
        logger.error(f"Gmail SMTP error: {str(e)}")
        raise

async def _render_template(template: str, context: dict) -> str:
    """Render email template with context"""
    
    # Simple template rendering
    # In production, use Jinja2 or similar
    templates = {
        "otp_verification": f"""
            <html>
            <body>
                <h2>Your Verification Code</h2>
                <p>Use this code to verify your email:</p>
                <h1 style="font-size: 32px; letter-spacing: 5px;">{context['otp']}</h1>
                <p>This code expires in {context.get('expiry_minutes', 10)} minutes.</p>
                <p>If you didn't request this, please ignore this email.</p>
            </body>
            </html>
        """,
        "welcome": f"""
            <html>
            <body>
                <h2>Welcome to Handled, {context['username']}!</h2>
                <p>We're excited to help you make better decisions.</p>
                <p>Get started by setting up your preferences.</p>
            </body>
            </html>
        """,
        "login_alert": f"""
            <html>
            <body>
                <h2>New Login Detected</h2>
                <p>Hello {context['username']},</p>
                <p>We detected a new login to your Handled account:</p>
                <ul>
                    <li><strong>Time:</strong> {context['time']}</li>
                    <li><strong>IP Address:</strong> {context['ip']}</li>
                    <li><strong>Device:</strong> {context.get('user_agent', 'Unknown')}</li>
                </ul>
                <p>If this was you, you can ignore this email.</p>
                <p>If you don't recognize this activity, please secure your account immediately.</p>
            </body>
            </html>
        """
    }
    
    return templates.get(template, "<html><body>Message from Handled</body></html>")

async def _queue_email_for_retry(to: str, subject: str, template: str, context: dict):
    """Queue failed email for retry using Redis"""
    
    redis = await get_redis()
    
    email_data = {
        "to": to,
        "subject": subject,
        "template": template,
        "context": context,
        "retry_count": 0,
        "created_at": datetime.utcnow().isoformat()
    }
    
    # Add to retry queue
    await redis.lpush("email:retry:queue", json.dumps(email_data))
    logger.info(f"Email queued for retry: {to}")
