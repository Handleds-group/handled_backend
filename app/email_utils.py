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
EMAIL_LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "images", "handled-app-icon.png")

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


def _logo_src() -> str:
    if not os.path.exists(EMAIL_LOGO_PATH):
        return ""

    mime_type, _ = mimetypes.guess_type(EMAIL_LOGO_PATH)
    mime_type = mime_type or "image/png"
    with open(EMAIL_LOGO_PATH, "rb") as logo_file:
        encoded = base64.b64encode(logo_file.read()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


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
      </td>
    </tr>
  </table>
</body>
</html>"""


def _hero(title: str, subtitle: str, badge: str | None = None) -> str:
    t = THEME
    badge_html = ""
    if badge:
        badge_html = f"""
          <tr>
            <td align="center" style="padding:0 0 14px 0;">
              <span style="display:inline-block; background:{t['badge_bg']}; color:{t['badge_text']}; border:1px solid #C7DAFE; border-radius:999px; padding:6px 12px; font-family:Segoe UI, Arial, sans-serif; font-size:11px; line-height:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.8px;">{badge}</span>
            </td>
          </tr>"""

    return f"""
      <tr>
        <td class="hero-pad" style="padding:36px 40px; background:linear-gradient(180deg, #F8F2FF 0%, #EEDFFF 100%); border-bottom:1px solid {t['border']};">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
            {badge_html}
            <tr>
              <td align="center" style="font-family:Segoe UI, Arial, sans-serif; color:{t['text']};">
                <h1 class="title" style="margin:0 0 10px; font-size:28px; line-height:36px; font-weight:700; color:{t['text']};">{title}</h1>
                <p class="body-text" style="margin:0; font-size:15px; line-height:24px; color:{t['text_soft']};">{subtitle}</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>"""


def _section_label(text: str) -> str:
    return f"""<p style="margin:0 0 14px; font-family:Segoe UI, Arial, sans-serif; font-size:11px; line-height:11px; font-weight:700; letter-spacing:1px; text-transform:uppercase; color:{THEME['text_muted']};">{text}</p>"""


def _panel(inner_html: str, accent: str | None = None, bg: str | None = None) -> str:
    t = THEME
    border_style = f"border-left:4px solid {accent};" if accent else ""
    panel_bg = bg or t["bg_soft"]
    return f"""
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{panel_bg}; border:1px solid {t['border']}; border-radius:16px; {border_style}">
        <tr>
          <td class="px py" style="padding:20px 22px;">
            {inner_html}
          </td>
        </tr>
      </table>"""


def _info_row(label: str, value: str, highlight: bool = False, last: bool = False) -> str:
    t = THEME
    border_bottom = "none" if last else f"1px solid {t['border']}"
    value_color = t["primary"] if highlight else t["text"]
    return f"""
      <tr>
        <td class="stack" style="width:42%; padding:11px 0; border-bottom:{border_bottom}; font-family:Segoe UI, Arial, sans-serif; font-size:12px; line-height:18px; font-weight:700; color:{t['text_muted']}; text-transform:uppercase; letter-spacing:0.6px;">{label}</td>
        <td class="stack center-sm" style="padding:11px 0; border-bottom:{border_bottom}; font-family:Segoe UI, Arial, sans-serif; font-size:14px; line-height:20px; font-weight:600; color:{value_color}; text-align:right;">{value}</td>
      </tr>"""
def _bullet_item(title: str, text: str, marker: str) -> str:
    t = THEME
    return f"""
      <tr>
        <td style="padding:0 0 14px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td style="width:38px; vertical-align:top; padding-top:2px;">
                <table role="presentation" width="28" cellpadding="0" cellspacing="0" border="0" style="width:28px; background:{t['primary_soft']}; border-radius:999px;">
                  <tr>
                    <td align="center" style="height:28px; font-family:Segoe UI, Arial, sans-serif; font-size:13px; line-height:28px; font-weight:700; color:{t['primary_dark']};">{marker}</td>
                  </tr>
                </table>
              </td>
              <td style="font-family:Segoe UI, Arial, sans-serif;">
                <p style="margin:0 0 4px; font-size:14px; line-height:20px; font-weight:700; color:{t['text']};">{title}</p>
                <p style="margin:0; font-size:13px; line-height:20px; color:{t['text_soft']};">{text}</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>"""


def _cta_button(label: str, url: str) -> str:
    t = THEME
    return f"""
      <table role="presentation" class="button" cellpadding="0" cellspacing="0" border="0" style="margin:0 auto;">
        <tr>
          <td align="center" style="border-radius:12px; background:{t['primary']};">
            <a href="{url}" target="_blank" style="display:inline-block; padding:14px 24px; font-family:Segoe UI, Arial, sans-serif; font-size:14px; line-height:14px; font-weight:700; color:#FFFFFF; background:{t['primary']}; border-radius:12px;">{label}</a>
          </td>
        </tr>
      </table>"""


def _message_bar(title: str, text: str, tone: str = "info") -> str:
    t = THEME
    styles = {
        "info": (t["primary"], t["bg_accent"], "#D6E4FF"),
        "success": (t["success"], t["success_bg"], "#B7E7C1"),
        "danger": (t["danger"], t["danger_bg"], "#F7C9C4"),
        "warning": (t["warning"], t["warning_bg"], "#FBD1A2"),
    }
    color, bg, border = styles[tone]
    return _panel(
        f"""
        <table role="presentation" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td style="vertical-align:top;">
              <p style="margin:0 0 4px; font-family:Segoe UI, Arial, sans-serif; font-size:13px; line-height:20px; font-weight:700; color:{color};">{title}</p>
              <p style="margin:0; font-family:Segoe UI, Arial, sans-serif; font-size:13px; line-height:20px; color:{THEME['text_soft']};">{text}</p>
            </td>
          </tr>
        </table>
        """,
        accent=color,
        bg=bg,
    ).replace(f"border:1px solid {t['border']};", f"border:1px solid {border};")


def otp_email_html(title: str, otp_code: str, purpose: str) -> str:
    t = THEME
    body = f"""
    {_hero(title, "Use the verification code below to confirm your identity. This code is valid for 10 minutes only.", badge="Verification Code")}
    <tr>
      <td class="px py" style="padding:36px 40px 32px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:24px;">
          <tr>
            <td align="center">
              <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="background:{t['bg_accent']}; border:1px solid #CFE0FF; border-radius:20px;">
                <tr>
                  <td class="otp-wrap" align="center" style="padding:26px 32px;">
                    <p style="margin:0 0 10px; font-family:Segoe UI, Arial, sans-serif; font-size:11px; line-height:11px; font-weight:700; letter-spacing:1.4px; text-transform:uppercase; color:{t['text_muted']};">Your OTP Code</p>
                    <p class="otp-code" style="margin:0; font-family:Segoe UI, Arial, sans-serif; font-size:38px; line-height:42px; font-weight:700; letter-spacing:8px; color:{t['text']};">{otp_code}</p>
                    <p style="margin:10px 0 0; font-family:Segoe UI, Arial, sans-serif; font-size:12px; line-height:18px; color:{t['text_muted']};">Expires in 10 minutes</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>

        {_panel(
            _section_label("Code Details")
            + f'''
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
              {_info_row("Purpose", purpose)}
              {_info_row("Length", "6 digits")}
              {_info_row("Expires", "10 minutes")}
              {_info_row("Usage", "One-time only", last=True)}
            </table>
            '''
        )}

        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:18px;">
          <tr>
            <td>
              {_message_bar("Security notice", "Never share this code with anyone. Handled staff will never ask for your OTP. If you did not request it, secure your account immediately.", tone="danger")}
            </td>
          </tr>
        </table>
      </td>
    </tr>"""
    return _shell(f"Your OTP: {otp_code} expires in 10 minutes", body)


def welcome_email_html(username: str) -> str:
    features = [
        ("Fast decisions", "Get clear guidance quickly whenever you are stuck between options.", "1"),
        ("Calm support", "Use the in-app calming experience before making an important choice.", "2"),
        ("Decision history", "Review past choices and patterns whenever you want to reflect.", "3"),
        ("Helpful reminders", "Stay on track with thoughtful notifications that are not overwhelming.", "4"),
    ]

    feature_rows = "".join(_bullet_item(title, text, marker) for title, text, marker in features)
    getting_started = [
        ("Open the app", "Your dashboard is ready and waiting for you.", "1"),
        ("Describe your situation", "Use Handle for me to get an informed suggestion.", "2"),
        ("Keep your progress", "Your activity is saved so you can revisit decisions later.", "3"),
    ]
    getting_started_rows = "".join(_bullet_item(title, text, marker) for title, text, marker in getting_started)

    body = f"""
    {_hero(f"Welcome to Handled, {username}", "Your account is ready. Handled is here to help you make decisions with more clarity and less stress.", badge="Account Verified")}
    <tr>
      <td class="px py" style="padding:36px 40px 32px;">
        <p class="body-text" style="margin:0 0 24px; font-family:Segoe UI, Arial, sans-serif; font-size:15px; line-height:24px; color:{THEME['text_soft']};">
          We are glad to have you here. Handled was built for moments when too many choices make it hard to move forward.
          Whether it is a daily decision or something more important, your account is ready to support you.
        </p>

        {_panel(_section_label("What You Can Do") + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{feature_rows}</table>')}

        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:18px;">
          <tr>
            <td>
              {_panel(_section_label("Get Started") + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{getting_started_rows}</table>')}
            </td>
          </tr>
        </table>

        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:24px;">
          <tr>
            <td align="center">
              {_cta_button("Open Handled", LANDING_PAGE_URL)}
            </td>
          </tr>
        </table>
      </td>
    </tr>"""

    return _shell(f"Welcome, {username}. Your Handled account is ready.", body)


def login_alert_email_html(login_time_utc: str, device: str = "Unknown device", location: str = "Unknown location", ip: str = None) -> str:
    session_rows = [
        _info_row("Time (UTC)", login_time_utc),
        _info_row("Device", device, last=not ip),
    ]
    if ip:
        session_rows.append(_info_row("IP Address", ip, last=True))
    body = f"""
    {_hero("New Login Detected", "We noticed a successful sign-in to your Handled account.", badge="Security")}
    <tr>
      <td class="px py" style="padding:36px 40px 32px;">
        {_message_bar("Quick check", "If this was you, no action is needed. If it was not you, change your password immediately.", tone="info")}

        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:18px;">
          <tr>
            <td>
              {_panel(
                  _section_label("Login Details")
                  + f'''
                  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                    {"".join(session_rows)}
                  </table>
                  '''
              )}
            </td>
          </tr>
        </table>

      </td>
    </tr>"""

    return _shell("A new login to your Handled account was recorded", body)


def payment_success_email_html(plan: str) -> str:
    plan_label = plan.capitalize()
    perks = {
        "pro": [
            ("Unlimited decisions", "Ask for guidance whenever you need it.", "1"),
            ("Full decision history", "Review your choices over time.", "2"),
            ("Priority notifications", "Receive the most important reminders first.", "3"),
            ("Advanced suggestions", "Get stronger support from the product.", "4"),
        ],
        "premium": [
            ("Everything in Pro", "Your account includes the full Pro experience.", "1"),
            ("Advanced AI access", "Use the most capable experience available in your plan.", "2"),
            ("Exclusive customization", "Enjoy additional premium product options.", "3"),
            ("Priority support", "Get faster help when you need it.", "4"),
        ],
        "free": [
            ("10 decisions per day", "A simple starting point for everyday choices.", "1"),
            ("Basic decision history", "Keep a light record of your activity.", "2"),
            ("Standard notifications", "Receive the essentials.", "3"),
            ("Mobile access", "Use Handled from your phone whenever you need it.", "4"),
        ],
    }
    perk_rows = "".join(_bullet_item(title, text, marker) for title, text, marker in perks.get(plan.lower(), perks["pro"]))

    body = f"""
    {_hero(f"Your {plan_label} plan is now active", "Your payment was successful and the new access level is available on your account right away.", badge=f"{plan_label} Active")}
    <tr>
      <td class="px py" style="padding:36px 40px 32px;">
        {_message_bar("Payment confirmed", f"Your {plan_label} features are now unlocked and ready to use.", tone="success")}

        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:18px;">
          <tr>
            <td>
              {_panel(_section_label(f"{plan_label} Benefits") + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{perk_rows}</table>')}
            </td>
          </tr>
        </table>

        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:24px;">
          <tr>
            <td align="center">
              {_cta_button("Open Handled", LANDING_PAGE_URL)}
            </td>
          </tr>
        </table>

        <p class="small-text" style="margin:14px 0 0; font-family:Segoe UI, Arial, sans-serif; font-size:12px; line-height:18px; color:{THEME['text_muted']}; text-align:center;">A receipt has been sent separately for your records.</p>
      </td>
    </tr>"""

    return _shell(f"Payment confirmed for your {plan_label} plan.", body)


def _format_currency(amount: int | None, currency: str | None) -> str:
    if amount is None or currency is None:
        return "Not available"
    try:
        return f"{amount / 100:,.2f} {currency.upper()}"
    except Exception:
        return f"{amount} {currency.upper() if currency else ''}"


def payment_receipt_email_html(
    plan: str,
    amount: int | None,
    currency: str | None,
    status: str,
    reference: str | None,
    payment_method: str | None = None,
    purchased_at: str | None = None,
    billing_reason: str | None = None,
) -> str:
    t = THEME
    plan_label = plan.capitalize() if plan else "Handled Subscription"
    amount_text = _format_currency(amount, currency)
    purchased_at_text = purchased_at or "Just now"
    payment_method_text = payment_method or "Card"
    status_text = status.capitalize() if status else "Completed"
    date_row = _info_row("Date", purchased_at_text, last=not billing_reason)
    billing_row = _info_row("Billing Reason", billing_reason, last=True) if billing_reason else ""
    status_tone = "success" if status_text.lower() in ("paid", "succeeded", "completed") else "warning"

    body = f"""
    {_hero("Payment Receipt", "Here is your receipt for the payment made on your Handled account. Please keep it for your records.", badge="Official Receipt")}
    <tr>
      <td class="px py" style="padding:36px 40px 32px;">
        {_message_bar("Transaction summary", f"Total charged: {amount_text}. Status: {status_text}.", tone=status_tone)}

        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:18px;">
          <tr>
            <td>
              {_panel(
                  _section_label("Transaction Details")
                  + f'''
                  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                    {_info_row("Plan", plan_label, highlight=True)}
                    {_info_row("Amount", amount_text)}
                    {_info_row("Currency", currency.upper() if currency else "N/A")}
                    {_info_row("Status", status_text)}
                    {_info_row("Reference", reference or "N/A")}
                    {_info_row("Payment Method", payment_method_text)}
                    {date_row}
                    {billing_row}
                  </table>
                  '''
              )}
            </td>
          </tr>
        </table>

        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:18px;">
          <tr>
            <td>
              {_panel(
                  _section_label("Included With This Payment")
                  + f'''
                  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                    {_bullet_item(plan_label, "Your selected subscription is active on your account.", "1")}
                    {_bullet_item("Saved reference", "The payment reference above can be used for support requests.", "2")}
                    {_bullet_item("Account access", "Features included in your plan are available based on your current subscription.", "3")}
                  </table>
                  '''
              )}
            </td>
          </tr>
        </table>

      </td>
    </tr>"""

    return _shell(f"Receipt for {amount_text} on your {plan_label} plan. Ref: {reference or 'N/A'}", body)


def account_deleted_email_html() -> str:
    body = f"""
    {_hero("Your account has been deleted", "Your Handled account and associated data have been permanently removed.", badge="Account Closed")}
    <tr>
      <td class="px py" style="padding:36px 40px 32px;">
        {_message_bar("Was this not you?", f"If you did not request this deletion, contact support immediately at {SUPPORT_EMAIL}.", tone="danger")}

        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:18px;">
          <tr>
            <td>
              {_panel(
                  _section_label("What Was Removed")
                  + f'''
                  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                    {_bullet_item("Account access", "Your login credentials and account access were removed.", "1")}
                    {_bullet_item("Decision history", "Saved decisions and related history were removed.", "2")}
                    {_bullet_item("Profile data", "Your profile information and preferences were removed.", "3")}
                    {_bullet_item("Subscription billing", "No further charges will be made for an active subscription.", "4")}
                  </table>
                  '''
              )}
            </td>
          </tr>
        </table>

        <p class="body-text" style="margin:20px 0 0; font-family:Segoe UI, Arial, sans-serif; font-size:14px; line-height:22px; text-align:center; color:{THEME['text_soft']};">
          If you want to use Handled again in the future, you can create a new account at
          <a href="{LANDING_PAGE_URL}" style="color:{THEME['primary']}; font-weight:700;">handleds.vercel.app</a>.
        </p>
      </td>
    </tr>"""

    return _shell("Your Handled account has been permanently deleted", body)


def account_deleted_with_reason_email_html(reason: Optional[str] = None, custom_message: Optional[str] = None) -> str:
    """
    Professional account deletion email with reason explanation
    
    Reasons can be:
    - "policy_violation" - Violated community guidelines
    - "payment_fraud" - Fraudulent payment activity detected
    - "fake_reports" - Submitted false bug reports
    - "spam_abuse" - Spam or abusive behavior
    - "inactive" - Account inactivity (>6 months)
    - "security" - Security/compromise concerns
    - "user_request" - User requested deletion
    - "other" - Other reason
    """
    
    reason_mapping = {
        "policy_violation": {
            "title": "Policy Violation",
            "description": "Your account was deleted due to violation of our Community Guidelines and Terms of Service.",
            "details": [
                "Engagement in prohibited activities",
                "Violation of our community standards",
                "Unethical or harmful behavior detected",
            ]
        },
        "payment_fraud": {
            "title": "Fraudulent Payment Activity",
            "description": "We detected fraudulent payment activity on your account.",
            "details": [
                "Suspicious payment patterns detected",
                "Chargeback or payment dispute filed",
                "Unauthorized access to billing information",
            ]
        },
        "fake_reports": {
            "title": "False Bug Reports",
            "description": "Your account submitted multiple false or misleading bug reports.",
            "details": [
                "Multiple non-reproducible reports submitted",
                "Spam bug reports detected",
                "Misuse of the bug reporting system",
            ]
        },
        "spam_abuse": {
            "title": "Spam or Abusive Behavior",
            "description": "Your account engaged in spam or abusive activities.",
            "details": [
                "Harassment or abusive communication",
                "Spam notifications or messages",
                "Disruptive behavior on the platform",
            ]
        },
        "inactive": {
            "title": "Account Inactivity",
            "description": "Your account was deleted due to extended inactivity.",
            "details": [
                "No activity for more than 6 months",
                "Account cleanup policy enforcement",
                "Inactive premium subscriptions terminated",
            ]
        },
        "security": {
            "title": "Security Concerns",
            "description": "Your account was deleted due to security concerns.",
            "details": [
                "Potential account compromise detected",
                "Multiple failed authentication attempts",
                "Suspicious login activity from unknown locations",
            ]
        },
        "user_request": {
            "title": "User Requested Deletion",
            "description": "Your account deletion was completed as requested.",
            "details": [
                "Your deletion request was processed",
                "All associated data has been removed",
                "Account closure completed successfully",
            ]
        },
        "other": {
            "title": "Account Deleted",
            "description": "Your Handled account has been deleted.",
            "details": [
                "Account and associated data removed",
                "All subscriptions canceled",
                "No further access available",
            ]
        }
    }
    
    reason_info = reason_mapping.get(reason, reason_mapping["other"])
    
    # Build the details list
    details_html = ""
    for i, detail in enumerate(reason_info["details"], 1):
        details_html += _bullet_item(detail, "", str(i))
    
    custom_message_html = (
        f'<p style="margin:20px 0; font-family:Segoe UI, Arial, sans-serif; font-size:14px; line-height:22px; color:{THEME["text_soft"]};">{custom_message}</p>'
        if custom_message else ""
    )
    
    body = f"""
    {_hero(reason_info['title'], reason_info['description'], badge="Account Deleted")}
    <tr>
      <td class="px py" style="padding:36px 40px 32px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td>
              {_panel(
                  _section_label("Deletion Reason")
                  + f'''
                  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                    {details_html}
                  </table>
                  '''
              )}
            </td>
          </tr>
        </table>

        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:24px;">
          <tr>
            <td>
              {_panel(
                  _section_label("What Was Removed")
                  + f'''
                  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                    {_bullet_item("Account access", "Your login credentials and all account access have been removed.", "1")}
                    {_bullet_item("Decision history", "All saved decisions and related history have been permanently deleted.", "2")}
                    {_bullet_item("Profile data", "Your profile information and preferences have been removed.", "3")}
                    {_bullet_item("Subscription billing", "Your subscription has been canceled. No further charges will be made.", "4")}
                  </table>
                  '''
              )}
            </td>
          </tr>
        </table>

        {_message_bar("Need Help?", f"If you believe this decision was made in error or have questions, contact our support team at {SUPPORT_EMAIL}.", tone="info")}
        
        {custom_message_html}
        
        <p class="body-text" style="margin:20px 0 0; font-family:Segoe UI, Arial, sans-serif; font-size:14px; line-height:22px; text-align:center; color:{THEME['text_soft']};">
          Thank you for being part of the Handled community.
        </p>
      </td>
    </tr>"""

    return _shell(f"{reason_info['title']} - Account Deletion", body)


def broadcast_notification_email_html(title: str, message: str) -> str:
    body = f"""
    {_hero(title, "A new message from your Handled admin team", badge="Notification")}
    <tr>
      <td class="px py" style="padding:36px 40px 32px;">
        {_panel(
            _section_label("Message Summary")
            + f'''
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
              <tr>
                <td>
                  <p style="margin:0; font-family:Segoe UI, Arial, sans-serif; font-size:14px; line-height:22px; color:{THEME['text']}; font-weight:700;">{title}</p>
                  <p style="margin:10px 0 0; font-family:Segoe UI, Arial, sans-serif; font-size:14px; line-height:24px; color:{THEME['text_soft']};">{message}</p>
                </td>
              </tr>
            </table>
            '''
        )}

        {_cta_button("Visit Handled", LANDING_PAGE_URL)}

        {_message_bar("Stay in the loop", "You will receive updates directly in your Handled inbox and email.", tone="info")}
      </td>
    </tr>"""
    return _shell(title, body)


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
