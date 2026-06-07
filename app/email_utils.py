from __future__ import annotations

import base64
import mimetypes
import os
import requests
from dotenv import load_dotenv
import fastapi
from typing import Optional

load_dotenv()

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM = os.getenv("RESEND_FROM")
EMAIL_DEBUG_ENABLED = os.getenv("EMAIL_DEBUG_ENABLED", "false").lower() == "true"
LANDING_PAGE_URL = os.getenv("LANDING_PAGE_URL", "https://handleds.vercel.app")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "support@handled.app")

# CHANGE: Using URL instead of local file path
# COMMENT OUT the old path: EMAIL_LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "images", "handled-app-icon.png")
# ADD the new URL - replace with your actual direct image URL
EMAIL_LOGO_URL = os.getenv("EMAIL_LOGO_URL", "https://i.ibb.co/zhhCmP6t/handled-app-icon.png")

THEME = {
    "bg_outer": "#F3EAFF",
    "bg_card": "#FFFFFF",
    "bg_soft": "#F7F1FF",
    "bg_accent": "#ECDDFF",
    "border": "#DCC8F4",
    "primary": "#7C3AED",
    "primary_dark": "#5B21B6",
    "primary_soft": "#E2D0FF",
    "success": "#15803D",
    "success_bg": "#ECFDF3",
    "danger": "#B42318",
    "danger_bg": "#FEF3F2",
    "warning": "#B54708",
    "warning_bg": "#FFF7ED",
    "text": "#24143F",
    "text_soft": "#4E3A73",
    "text_muted": "#6F5A96",
    "badge_bg": "#E9D8FF",
    "badge_text": "#5B21B6",
}

# REMOVED the old _logo_src() function that used base64 encoding
# ADDED new function to use URL directly
def _logo_src() -> str:
    """Return the logo URL instead of base64 encoded image"""
    return EMAIL_LOGO_URL

def _brand_logo(size: int = 64) -> str:
    logo_src = _logo_src()
    if not logo_src:
        return ""

    return (
        f'<img src="{logo_src}" alt="Handled" width="{size}" height="{size}" '
        f'style="display:block; width:{size}px; height:{size}px; border-radius:16px;" />'
    )


def _shell(preheader: str, body_html: str) -> str:
    t = THEME
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="light">
  <meta name="supported-color-schemes" content="light">
  <title>Handled</title>
  <!--[if mso]><noscript><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml></noscript><![endif]-->
  <style>
    body, table, td, a {{ -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
    table, td {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
    img {{ -ms-interpolation-mode: bicubic; border: 0; outline: none; text-decoration: none; display: block; }}
    table {{ border-collapse: collapse !important; }}
    body {{ margin: 0 !important; padding: 0 !important; width: 100% !important; height: 100% !important; background: {t['bg_outer']}; }}
    a {{ color: {t['primary']}; text-decoration: none; }}
    @media only screen and (max-width: 600px) {{
      .container {{ width: 100% !important; }}
      .stack {{ display: block !important; width: 100% !important; }}
      .px {{ padding-left: 20px !important; padding-right: 20px !important; }}
      .py {{ padding-top: 24px !important; padding-bottom: 24px !important; }}
      .hero-pad {{ padding: 28px 20px !important; }}
      .title {{ font-size: 24px !important; line-height: 32px !important; }}
      .body-text {{ font-size: 14px !important; line-height: 22px !important; }}
      .small-text {{ font-size: 12px !important; line-height: 18px !important; }}
      .otp-wrap {{ padding: 22px 16px !important; }}
      .otp-code {{ font-size: 30px !important; letter-spacing: 6px !important; }}
      .button {{ display: block !important; width: 100% !important; }}
      .button a {{ display: block !important; width: 100% !important; text-align: center !important; box-sizing: border-box; }}
      .center-sm {{ text-align: center !important; }}
    }}
  </style>
</head>
<body style="margin:0; padding:0; background:{t['bg_outer']};">
  <div style="display:none; max-height:0; overflow:hidden; opacity:0; mso-hide:all;">
    {preheader}
  </div>

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{t['bg_outer']};">
    <tr>
      <td align="center" style="padding: 24px 12px;">
        <table role="presentation" class="container" width="600" cellpadding="0" cellspacing="0" border="0" style="width:600px; max-width:600px;">
          <tr>
            <td align="center" style="padding: 0 0 20px 0;">
              <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="font-family:Segoe UI, Arial, sans-serif; font-size:20px; line-height:20px; font-weight:700; color:{t['text']};">
                    {_brand_logo(64)}
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <tr>
            <td style="background:{t['bg_card']}; border:1px solid {t['border']}; border-radius:24px; overflow:hidden; box-shadow:0 12px 28px rgba(15, 23, 42, 0.08);">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                {body_html}
              </table>
            </td>
          </tr>

          <tr>
            <td align="center" style="padding:20px 12px 0; font-family:Segoe UI, Arial, sans-serif; color:{t['text_muted']};">
              <p style="margin:0; font-size:11px; line-height:17px;">Handled &middot; Florida, United States</p>
            </td>
          </tr>
        </table>
      </table>
    </table>
  </table>
</body>
</html>"""


# The rest of your functions remain the same (hero, panel, info_row, bullet_item, etc.)
# ... [all your other email template functions remain unchanged] ...

def send_email_with_error(subject: str, email_to: str, body: str) -> tuple[bool, str | None]:
    if not RESEND_API_KEY:
        return False, "missing RESEND_API_KEY in environment"
    if not RESEND_FROM:
        return False, "missing RESEND_FROM in environment"

    try:
        if EMAIL_DEBUG_ENABLED:
            print(f"[Handled Email] Sending to {email_to} via Resend")

        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": RESEND_FROM,
                "to": [email_to],
                "subject": subject,
                "html": body,
            },
            timeout=20,
        )
        response.raise_for_status()
        return True, None
    except Exception as exc:
        try:
            error_body = response.text
        except Exception:
            error_body = None
        if error_body:
            return False, f"Resend send failed: {exc} | response: {error_body}"
        return False, f"Resend send failed: {exc}"


def send_email(subject: str, email_to: str, body: str) -> bool:
    success, error = send_email_with_error(subject, email_to, body)
    if not success:
        print(f"[Handled Email Error] {error}")
    return success