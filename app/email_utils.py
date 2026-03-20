import smtplib
import os
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_THEME_COLOR = os.getenv("EMAIL_THEME_COLOR", "5B2AA8")  # default darker purple

BG_COLOR = "#F3ECFF"
CARD_BG = "#FFFFFF"
BORDER_COLOR = "#E4D7FF"
MUTED_TEXT = "#6B5A8A"
TEXT_COLOR = "#3F325B"

def _render_email_shell(title: str, subtitle: str, content_html: str, footer_note: str | None = None) -> str:
    footer = footer_note or "If you didn't request this email, you can safely ignore it."
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG_COLOR}; padding:24px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px; background:{CARD_BG}; border:1px solid {BORDER_COLOR}; border-radius:16px; overflow:hidden;">
            <tr>
              <td style="padding:18px 22px; background:#E9DDFF;">
                <h1 style="margin:0; font-family:Arial, sans-serif; font-size:22px; color:#{EMAIL_THEME_COLOR};">Handled</h1>
                <p style="margin:6px 0 0; font-family:Arial, sans-serif; color:{MUTED_TEXT}; font-size:13px;">{subtitle}</p>
              </td>
            </tr>
            <tr>
              <td style="padding:22px; font-family:Arial, sans-serif; color:{TEXT_COLOR};">
                <h2 style="margin:0 0 10px; font-size:18px; color:#{EMAIL_THEME_COLOR};">{title}</h2>
                {content_html}
                <p style="margin:18px 0 0; font-size:12px; color:{MUTED_TEXT};">{footer}</p>
              </td>
            </tr>
          </table>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;">
            <tr>
              <td style="padding-top:10px; text-align:center; font-family:Arial, sans-serif; font-size:11px; color:{MUTED_TEXT};">
                Handled • Secure Messages • 2026
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
    <p style="margin:0 0 12px; font-size:14px;">Welcome {username}! We’re happy you’re here.</p>
    <div style="background:#F7F3FF; border:1px solid {BORDER_COLOR}; padding:12px; border-radius:10px; font-size:13px; color:{MUTED_TEXT};">
      <div style="font-weight:700; color:#{EMAIL_THEME_COLOR}; margin-bottom:6px;">Getting started</div>
      <div>• Verify your email</div>
      <div>• Complete your profile</div>
      <div>• Explore decisions and history</div>
    </div>
    """
    return _render_email_shell(title="Welcome to Handled", subtitle="Let’s get you set up", content_html=content)

def login_alert_email_html(login_time_utc: str) -> str:
    content = f"""
    <p style="margin:0 0 12px; font-size:14px;">We detected a login to your account.</p>
    <div style="background:#F7F3FF; border:1px solid {BORDER_COLOR}; padding:12px; border-radius:10px; font-size:13px; color:{MUTED_TEXT};">
      <div>Time (UTC): {login_time_utc}</div>
      <div>If this wasn’t you, change your password immediately.</div>
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
    return _render_email_shell(title="Account deleted", subtitle="We’re sorry to see you go", content_html=content)

def send_email(subject: str, email_to: str, body: str, cta_text: str = None, cta_link: str = None):
    """
    Sends a daisy-like, detailed HTML email using smtplib.
    Optional CTA button: cta_text + cta_link
    """

    cta_html = ""
    if cta_text and cta_link:
        cta_html = f"""
        <div style='text-align: center; margin: 20px 0;'>
            <a href="{cta_link}" 
               style='background-color: #{EMAIL_THEME_COLOR}; color: white; padding: 12px 25px; text-decoration: none; border-radius: 8px; display: inline-block; font-weight: bold;'>
               {cta_text}
            </a>
        </div>
        """

    html_body = f"""
    <div style='font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; background-color: #F5F3FF; padding: 30px; border-radius: 15px; max-width: 600px; margin: auto; box-shadow: 0 4px 12px rgba(0,0,0,0.1);'>
        
        <!-- Header -->
        <div style='text-align: center; margin-bottom: 25px;'>
            <h1 style='color: #{EMAIL_THEME_COLOR}; font-size: 28px; margin:0;'>Handled App</h1>
            <p style='color: #{EMAIL_THEME_COLOR}; margin-top: 5px; font-size: 16px;'>Your personal ADHD & decision assistant</p>
        </div>

        <!-- Body Content -->
        <div style='padding: 20px; background-color: #FFFFFF; border-radius: 12px;'>
            <p style='font-size: 16px; color:#4B5563; line-height: 1.6;'>Hi there,</p>
            <p style='font-size: 16px; color:#4B5563; line-height: 1.6;'>{body}</p>
            {cta_html}
            <p style='font-size: 14px; color:#9CA3AF; margin-top: 25px;'>If you didn't request this email, you can safely ignore it.</p>
        </div>

        <!-- Footer -->
        <div style='text-align: center; margin-top: 20px; font-size: 13px; color:#9CA3AF;'>
            <p>Handled App &copy; 2026</p>
            <p>Need help? Contact us at <a href='mailto:{EMAIL_FROM}' style='color:#{EMAIL_THEME_COLOR};'>{EMAIL_FROM}</a></p>
        </div>

    </div>
    """

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = EMAIL_FROM
    msg['To'] = email_to
    msg.set_content("This email requires an HTML compatible email client.")
    msg.add_alternative(html_body, subtype='html')

    if not all([SMTP_SERVER, SMTP_USERNAME, SMTP_PASSWORD, EMAIL_FROM]):
        raise RuntimeError("Email settings are not fully configured in environment")

    # Send email
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print("Error sending email:", e)
        raise e
