# utils.py - Email sending with multiple providers

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging

logger = logging.getLogger(__name__)

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