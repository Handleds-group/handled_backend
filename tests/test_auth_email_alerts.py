import os
from types import SimpleNamespace

os.environ.setdefault("NEON_DB", "postgresql://user:pass@localhost:5432/test")
os.environ.setdefault("SUPABASE_DB", "postgresql://user:pass@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ACCESS_TOKEN_SECRET", "test-access-secret")
os.environ.setdefault("REFRESH_TOKEN_SECRET", "test-refresh-secret")

from app.auth import login_alert_email_html, logout, queue_logout_alert_email, send_email


class FakeBackgroundTasks:
    def __init__(self):
        self.tasks = []

    def add_task(self, func, **kwargs):
        self.tasks.append((func, kwargs))


class FakeHeaders(dict):
    def get(self, key, default=None):
        return super().get(key.lower(), default)


def test_logout_route_queues_only_logout_alert():
    background_tasks = FakeBackgroundTasks()
    request = SimpleNamespace(
        headers=FakeHeaders({"user-agent": "Windows"}),
        client=SimpleNamespace(host="203.0.113.10"),
    )
    current_user = SimpleNamespace(email="user@example.com")

    response = logout(
        request=request,
        background_tasks=background_tasks,
        current_user=current_user,
    )

    assert response == {"message": "Logged out successfully"}
    assert len(background_tasks.tasks) == 1

    func, kwargs = background_tasks.tasks[0]
    assert func is send_email
    assert kwargs["subject"] == "Logout confirmed"
    assert kwargs["email_to"] == "user@example.com"
    assert "Logout Confirmed" in kwargs["body"]
    assert "New Login Detected" not in kwargs["body"]


def test_logout_email_helper_does_not_use_login_template():
    background_tasks = FakeBackgroundTasks()

    queue_logout_alert_email(
        background_tasks,
        email="user@example.com",
        logout_time_utc="2026-05-31 12:00:00 UTC",
        device="Windows PC",
        ip="203.0.113.10",
    )

    _, kwargs = background_tasks.tasks[0]
    assert kwargs["body"] != login_alert_email_html(
        login_time_utc="2026-05-31 12:00:00 UTC",
        device="Windows PC",
        ip="203.0.113.10",
    )
    assert "Logout Details" in kwargs["body"]
