from app.email_utils import logout_alert_email_html


def test_logout_alert_email_uses_logout_copy():
    html = logout_alert_email_html(
        logout_time_utc="2026-05-25 10:00:00 UTC",
        device="Windows PC",
        ip="203.0.113.10",
    )

    assert "Logout Confirmed" in html
    assert "Logout Details" in html
    assert "Your Handled account was signed out" in html
    assert "New Login Detected" not in html
    assert "A new login to your Handled account was recorded" not in html
