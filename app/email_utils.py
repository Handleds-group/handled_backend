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
EMAIL_THEME_COLOR = os.getenv("EMAIL_THEME_COLOR", "A78BFA")  # default light purple

async def send_email(subject: str, email_to: str, body: str, cta_text: str = None, cta_link: str = None):
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
            <p style='font-size: 14px; color:#9CA3AF; margin-top: 25px;'>If you didn’t request this email, you can safely ignore it.</p>
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

    # Send email
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print("Error sending email:", e)
        raise e