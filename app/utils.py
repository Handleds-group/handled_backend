# utils.py - Shared utilities (auth, rate limiting, idempotency, email)

import json
import os
import logging
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Callable, Any, Awaitable
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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

# -------------------------------------------------------------------
# Email sending with SMTP (Gmail)
# -------------------------------------------------------------------

async def send_email(
    to: str, 
    subject: str, 
    template: str, 
    context: dict,
    provider: Optional[str] = None
) -> bool:
    """Send email using Gmail SMTP"""
    
    try:
        return await _send_via_gmail(to, subject, template, context)
            
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {str(e)}")
        
        # Queue for retry if enabled
        if os.getenv("EMAIL_QUEUE_ENABLED") == "True":
            await _queue_email_for_retry(to, subject, template, context)
        
        return False

async def _send_via_gmail(to: str, subject: str, template: str, context: dict) -> bool:
    """Send via Gmail SMTP with app password"""
    
    gmail_user = os.getenv("GMAIL_ADDRESS")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "")  # Remove spaces
    
    if not gmail_user or not gmail_password:
        logger.error("Gmail credentials not configured")
        return False
    
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
        return False

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

async def _render_template(template: str, context: dict) -> str:
    """Render email template with modern purple UI"""

    base_style = """
    <style>
        body {
            margin: 0;
            padding: 0;
            background: #0a0718;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }
        .container {
            width: 100%;
            padding: 40px 20px;
            background: #0a0718;
        }
        .card {
            max-width: 560px;
            margin: 0 auto;
            background: #140f29;
            border-radius: 24px;
            overflow: hidden;
            box-shadow: 0 20px 40px -12px rgba(106, 13, 173, 0.3);
            border: 1px solid #2d1f5e;
        }
        .header {
            background: linear-gradient(145deg, #7C3AED, #9d4edd);
            padding: 32px 40px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            color: white;
            font-size: 28px;
            font-weight: 600;
            letter-spacing: -0.5px;
        }
        .header p {
            margin: 8px 0 0;
            color: rgba(255, 255, 255, 0.9);
            font-size: 16px;
        }
        .content {
            padding: 40px;
            background: #140f29;
        }
        .content h2 {
            margin: 0 0 16px;
            color: #e2d9ff;
            font-size: 24px;
            font-weight: 600;
        }
        .content p {
            margin: 0 0 24px;
            color: #b4a6d9;
            font-size: 16px;
            line-height: 1.6;
        }
        .otp-box {
            background: #1e1737;
            border: 2px solid #3b2b6b;
            border-radius: 16px;
            padding: 24px;
            margin: 24px 0;
            text-align: center;
        }
        .otp-code {
            font-size: 48px;
            font-weight: 700;
            letter-spacing: 12px;
            color: #c4b5fd;
            font-family: 'Courier New', monospace;
            text-shadow: 0 0 20px rgba(157, 78, 221, 0.5);
        }
        .otp-expiry {
            color: #9d8bb8;
            font-size: 14px;
            margin-top: 16px;
        }
        .info-box {
            background: #1e1737;
            border-radius: 16px;
            padding: 24px;
            margin: 24px 0;
            border-left: 4px solid #9d4edd;
        }
        .info-box p {
            margin: 8px 0;
            color: #c4b5fd;
        }
        .info-box strong {
            color: #e2d9ff;
            font-weight: 600;
        }
        .warning-box {
            background: #2d1f2d;
            border-radius: 16px;
            padding: 20px;
            margin: 24px 0;
            border-left: 4px solid #f87171;
        }
        .warning-box p {
            margin: 0;
            color: #fecaca;
        }
        .success-box {
            background: #1a2d2a;
            border-radius: 16px;
            padding: 20px;
            margin: 24px 0;
            border-left: 4px solid #4ade80;
        }
        .success-box p {
            margin: 0;
            color: #bbf7d0;
        }
        .button {
            display: inline-block;
            background: #9d4edd;
            color: white;
            text-decoration: none;
            padding: 14px 32px;
            border-radius: 40px;
            font-weight: 600;
            font-size: 16px;
            margin: 16px 0;
            box-shadow: 0 8px 20px -8px #7C3AED;
        }
        .footer {
            padding: 32px 40px;
            background: #0f0b1f;
            text-align: center;
            border-top: 1px solid #2d1f5e;
        }
        .footer p {
            margin: 4px 0;
            color: #6b5b95;
            font-size: 14px;
        }
        .footer a {
            color: #9d4edd;
            text-decoration: none;
        }
        ul {
            margin: 16px 0;
            padding-left: 20px;
        }
        li {
            color: #b4a6d9;
            margin: 8px 0;
        }
    </style>
    """

    templates = {
        "otp_verification": f"""
        <html>
        <head>
            {base_style}
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        </head>
        <body>
            <div class="container">
                <div class="card">
                    <div class="header">
                        <h1>✨ Handled</h1>
                        <p>Verify your email address</p>
                    </div>
                    <div class="content">
                        <h2>Welcome to Handled</h2>
                        <p>You're just one step away from a calmer, more organized mind. Use the verification code below to complete your signup.</p>
                        
                        <div class="otp-box">
                            <div class="otp-code">{context['otp']}</div>
                            <div class="otp-expiry">⏱️ Expires in {context.get('expiry_minutes', 10)} minutes</div>
                        </div>
                        
                        <p>This code helps us make sure it's really you. Never share this code with anyone, not even our team.</p>
                        
                        <div class="info-box">
                            <p><strong>🌟 Why verify?</strong></p>
                            <p>✓ Secure your account</p>
                            <p>✓ Get important updates</p>
                            <p>✓ Personalized experience</p>
                        </div>
                    </div>
                    <div class="footer">
                        <p>© 2024 Handled. All rights reserved.</p>
                        <p>Making decisions easier, one step at a time.</p>
                        <p><a href="#">Help Center</a> • <a href="#">Privacy</a> • <a href="#">Terms</a></p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """,

        "welcome": f"""
        <html>
        <head>
            {base_style}
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        </head>
        <body>
            <div class="container">
                <div class="card">
                    <div class="header">
                        <h1>🎉 Welcome to Handled!</h1>
                        <p>Your journey begins now</p>
                    </div>
                    <div class="content">
                        <h2>Hello {context['username']}!</h2>
                        <p>We're thrilled to have you join our community. Handled is designed to help you make better decisions, reduce overwhelm, and find your calm.</p>
                        
                        <div class="info-box">
                            <p><strong>✨ Here's what you can do:</strong></p>
                            <p>🧠 Make clearer decisions</p>
                            <p>🎮 Play calming focus games</p>
                            <p>📊 Track your progress</p>
                            <p>🤝 Connect with others</p>
                        </div>
                        
                        <center>
                            <a href="#" class="button">Start Your Journey</a>
                        </center>
                        
                        <p style="text-align: center; margin-top: 24px;">Take a deep breath. You've got this. 💜</p>
                    </div>
                    <div class="footer">
                        <p>© 2024 Handled. All rights reserved.</p>
                        <p>Stay calm, stay focused, stay handled.</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """,

        "login_alert": f"""
        <html>
        <head>
            {base_style}
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        </head>
        <body>
            <div class="container">
                <div class="card">
                    <div class="header">
                        <h1>🔐 Security Alert</h1>
                        <p>New sign-in to your account</p>
                    </div>
                    <div class="content">
                        <h2>Hi {context['username']}</h2>
                        <p>We noticed a new login to your Handled account. If this was you, no action is needed. If not, please secure your account immediately.</p>
                        
                        <div class="info-box">
                            <p><strong>📱 Sign-in Details:</strong></p>
                            <p>🕐 <strong>Time:</strong> {context['time']}</p>
                            <p>🌍 <strong>IP Address:</strong> {context['ip']}</p>
                            <p>📱 <strong>Device:</strong> {context.get('user_agent', 'Unknown')[:50]}...</p>
                        </div>
                        
                        <div class="warning-box">
                            <p><strong>⚠️ Didn't recognize this?</strong></p>
                            <p style="margin-top: 8px;">Reset your password immediately and contact our support team.</p>
                        </div>
                        
                        <center>
                            <a href="#" class="button">Review Activity</a>
                        </center>
                    </div>
                    <div class="footer">
                        <p>© 2024 Handled. All rights reserved.</p>
                        <p>Your security is our priority 🔐</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """,

        "password_reset": f"""
        <html>
        <head>
            {base_style}
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        </head>
        <body>
            <div class="container">
                <div class="card">
                    <div class="header">
                        <h1>🔄 Reset Your Password</h1>
                        <p>We've got you covered</p>
                    </div>
                    <div class="content">
                        <h2>Hello {context['username']}</h2>
                        <p>We received a request to reset your Handled account password. Use the code below to create a new one.</p>
                        
                        <div class="otp-box">
                            <div class="otp-code">{context['otp']}</div>
                            <div class="otp-expiry">⏱️ Code expires in {context.get('expiry_minutes', 10)} minutes</div>
                        </div>
                        
                        <div class="warning-box">
                            <p><strong>🔴 Didn't request this?</strong></p>
                            <p style="margin-top: 8px;">If you didn't request a password reset, please ignore this email. Your account is still secure.</p>
                        </div>
                        
                        <div class="info-box">
                            <p><strong>🛡️ Security Tips:</strong></p>
                            <p>• Never share this code</p>
                            <p>• Use a strong, unique password</p>
                            <p>• Enable 2FA for extra security</p>
                        </div>
                    </div>
                    <div class="footer">
                        <p>© 2024 Handled. All rights reserved.</p>
                        <p>Making decisions easier, one step at a time.</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """,

        "password_changed": f"""
        <html>
        <head>
            {base_style}
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        </head>
        <body>
            <div class="container">
                <div class="card">
                    <div class="header">
                        <h1>✅ Password Changed</h1>
                        <p>Your account is secure</p>
                    </div>
                    <div class="content">
                        <h2>Hi {context['username']}</h2>
                        
                        <div class="success-box">
                            <p><strong>✓ Your password was successfully changed</strong></p>
                        </div>
                        
                        <div class="info-box">
                            <p><strong>📋 Change Details:</strong></p>
                            <p>🕐 <strong>Time:</strong> {context['time']}</p>
                            <p>🌍 <strong>IP Address:</strong> {context['ip']}</p>
                        </div>
                        
                        <div class="warning-box">
                            <p><strong>⚠️ Didn't make this change?</strong></p>
                            <p style="margin-top: 8px;">Contact support immediately to secure your account.</p>
                        </div>
                        
                        <p style="text-align: center; margin-top: 24px;">Stay safe out there! 💜</p>
                    </div>
                    <div class="footer">
                        <p>© 2024 Handled. All rights reserved.</p>
                        <p>Stay calm, stay focused, stay handled.</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
    }

    return templates.get(template, f"""
    <html>
    <head>{base_style}</head>
    <body>
        <div class="container">
            <div class="card">
                <div class="header">
                    <h1>Handled</h1>
                </div>
                <div class="content">
                    <p>You have a new notification from Handled.</p>
                </div>
                <div class="footer">
                    <p>© 2024 Handled</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """)

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
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
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
                    detail="Rate limit exceeded. Please try again later."
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
                    detail="Duplicate request detected"
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
    # Also add to blacklist version if needed
    await redis.incr(f"user:version:{user_id}")

# -------------------------------------------------------------------
# Uploads (placeholder)
# -------------------------------------------------------------------

async def upload_to_cdn(file, folder: str = "uploads") -> str:
    """Simple local file upload (replace with cloud storage in production)"""
    os.makedirs(folder, exist_ok=True)
    file_path = os.path.join(folder, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())
    return f"/{folder}/{file.filename}"

# -------------------------------------------------------------------
# Kill switch
# -------------------------------------------------------------------

def kill_switch() -> bool:
    """Check if maintenance mode is enabled"""
    return os.getenv("MAINTENANCE_MODE", "False") == "True"

# -------------------------------------------------------------------
# Health checks (add these to main.py)
# -------------------------------------------------------------------

async def check_database_health(db: AsyncSession) -> bool:
    """Check database connectivity"""
    try:
        await db.execute("SELECT 1")
        return True
    except Exception:
        return False

async def check_redis_health(redis) -> bool:
    """Check Redis connectivity"""
    try:
        await redis.ping()
        return True
    except Exception:
        return False