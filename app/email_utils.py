import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM") or SMTP_USERNAME
EMAIL_THEME_COLOR = os.getenv("EMAIL_THEME_COLOR", "5B2AA8")  # default darker purple
EMAIL_DEBUG_ENABLED = os.getenv("EMAIL_DEBUG_ENABLED", "false").lower() == "true"
LANDING_PAGE_URL = "https://handleds.vercel.app"

BG_COLOR = "#E3D7F8"
CARD_BG = "#F6F3F3"
BORDER_COLOR = "#E4D7FF"
MUTED_TEXT = "#665487"
TEXT_COLOR = "#40315F"

def _render_email_shell(title: str, subtitle: str, content_html: str, footer_note: str | None = None) -> str:
    footer = footer_note or "If you didn't request this email, you can safely ignore it."
    clarification_html = (
        f'Visit our offical site <a href="{LANDING_PAGE_URL}" '
        f'style="color:#{EMAIL_THEME_COLOR}; text-decoration:none; font-weight:600;">handleds.vercel.app</a>.'
    )
    logo_src = "https://handleds.vercel.app/handled-app-icon.png"
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG_COLOR}; padding:24px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px; background:{CARD_BG}; border:1px solid {BORDER_COLOR}; border-radius:16px; overflow:hidden;">
            <tr>
              <td style="padding:18px 22px; background:#E9DDFF;">
                <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;">
                  <tr>
                    <td align="center" style="padding-bottom:10px;">
                      <a href="{LANDING_PAGE_URL}" style="text-decoration:none;">
                        <img src="{logo_src}" alt="Handled icon" width="96" height="96" style="display:block; width:96px; height:96px; border-radius:50%; border:3px solid #E1D2FF; background:#F6F3F3;">
                      </a>
                    </td>
                  </tr>
                  <tr>
                    <td align="center">
                      <h1 style="margin:0; font-family:Arial, sans-serif; font-size:22px; color:#{EMAIL_THEME_COLOR};">Handled</h1>
                    </td>
                  </tr>
                </table>
                <p style="margin:6px 0 0; font-family:Arial, sans-serif; color:{MUTED_TEXT}; font-size:13px;">{subtitle}</p>
              </td>
            </tr>
            <tr>
              <td style="padding:22px; font-family:Arial, sans-serif; color:{TEXT_COLOR};">
                <h2 style="margin:0 0 10px; font-size:18px; color:#{EMAIL_THEME_COLOR};">{title}</h2>
                {content_html}
                <p style="margin:18px 0 0; font-size:12px; color:{MUTED_TEXT};">{footer}</p>
                <p style="margin:8px 0 0; font-size:12px; color:{MUTED_TEXT};">{clarification_html}</p>
              </td>
            </tr>
          </table>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;">
            <tr>
              <td style="padding-top:10px; text-align:center; font-family:Arial, sans-serif; font-size:11px; color:{MUTED_TEXT};">
                Handled &bull; Secure Messages &bull; 2026
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
    """

def otp_email_html(title: str, otp_code: str, purpose: str) -> str:
    content = f"""
    <p style="margin:0 0 12px; font-size:14px;">Use the one-time code below to continue.</p>
    <div style="text-align:center; margin:16px 0;">
      <span style="display:inline-block; background:#EFE3FF; color:#{EMAIL_THEME_COLOR}; padding:12px 22px; border-radius:10px; font-size:24px; letter-spacing:3px; font-weight:700;">
        {otp_code}
      </span>
    </div>
    <div style="background:#F7F3FF; border:1px dashed #D8C6F7; padding:12px; border-radius:10px; font-size:12px; color:{MUTED_TEXT};">
      <div style="font-weight:700; color:#{EMAIL_THEME_COLOR}; margin-bottom:6px;">OTP Details</div>
      <div>Purpose: {purpose}</div>
      <div>Length: 6 digits</div>
      <div>Expires in: 10 minutes</div>
      <div>One-time use only</div>
    </div>
    """
    return _render_email_shell(title=title, subtitle="Your personal ADHD & decision assistant", content_html=content)

def welcome_email_html(username: str) -> str:
    content = f"""
    <p style="margin:0 0 12px; font-size:14px;">Welcome {username}! We're happy you're here.</p>
    <div style="background:#F7F3FF; border:1px solid {BORDER_COLOR}; padding:12px; border-radius:10px; font-size:13px; color:{MUTED_TEXT};">
      <div style="font-weight:700; color:#{EMAIL_THEME_COLOR}; margin-bottom:6px;">Getting started</div>
      <div>&bull; Verify your email</div>
      <div>&bull; Complete your profile</div>
      <div>&bull; Explore decisions and history</div>
    </div>
    """
    return _render_email_shell(title="Welcome to Handled", subtitle="Let's get you set up", content_html=content)

def login_alert_email_html(login_time_utc: str) -> str:
    content = f"""
    <p style="margin:0 0 12px; font-size:14px;">We detected a login to your account.</p>
    <div style="background:#F7F3FF; border:1px solid {BORDER_COLOR}; padding:12px; border-radius:10px; font-size:13px; color:{MUTED_TEXT};">
      <div>Time (UTC): {login_time_utc}</div>
      <div>If this wasn't you, change your password immediately.</div>
    </div>
    """
    return _render_email_shell(title="New login detected", subtitle="Security notice", content_html=content)

def account_deleted_email_html() -> str:
    content = """
    <p style="margin:0 0 12px; font-size:14px;">Your Handled account has been deleted.</p>
    <div style="background:#F7F3FF; border:1px solid #E4D7FF; padding:12px; border-radius:10px; font-size:13px; color:#6B5A8A;">
      <div>If this was not you, contact support right away.</div>
    </div>
    """
    return _render_email_shell(title="Account deleted", subtitle="We're sorry to see you go", content_html=content)

def payment_success_email_html(plan: str) -> str:
    plan_label = plan.capitalize()
    content = f"""
    <p style="margin:0 0 12px; font-size:14px;">Your payment was successful.</p>
    <div style="background:#F7F3FF; border:1px dashed #D8C6F7; padding:12px; border-radius:10px; font-size:13px; color:{MUTED_TEXT};">
      <div style="font-weight:700; color:#{EMAIL_THEME_COLOR}; margin-bottom:6px;">Payment summary</div>
      <div><strong>Plan:</strong> {plan_label}</div>
      <div><strong>Status:</strong> Active</div>
      <div><strong>Access:</strong> Premium features enabled</div>
      <div style="margin-top:8px;">Thanks for supporting Handled.</div>
    </div>
    """
    return _render_email_shell(title="Payment Successful", subtitle="Subscription activated", content_html=content)

def send_email_with_error(subject: str, email_to: str, body: str) -> tuple[bool, str | None]:
    """
    Sends an HTML email using SMTP.
    Returns (success, error_message).
    """
    if not SMTP_SERVER:
        return False, "missing SMTP_SERVER in environment"
    if not SMTP_PORT:
        return False, "missing SMTP_PORT in environment"
    if not EMAIL_FROM:
        return False, "missing EMAIL_FROM or SMTP_USERNAME in environment"
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        return False, "missing SMTP_USERNAME or SMTP_PASSWORD in environment"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = email_to
    msg.set_content("Please view this email in an HTML capable client.")
    msg.add_alternative(body, subtype="html")

    try:
        if EMAIL_DEBUG_ENABLED:
            print(f"Sending email via SMTP to {email_to} using {SMTP_SERVER}:{SMTP_PORT}")

        if SMTP_PORT == 465:
            smtp_client = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=20)
        else:
            smtp_client = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20)

        with smtp_client as smtp:
            smtp.ehlo()
            if SMTP_PORT != 465:
                smtp.starttls()
                smtp.ehlo()
            smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(msg)

        return True, None
    except Exception as exc:
        return False, str(exc)

def send_email(subject: str, email_to: str, body: str) -> bool:
    """
    Sends an HTML email using SMTP.
    Returns True on success, False on failure.
    """
    success, error = send_email_with_error(subject, email_to, body)
    if not success:
        print("Error sending email via SMTP:", error)
    return success
