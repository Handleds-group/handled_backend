import os
from datetime import datetime, timedelta, timezone

from app.idempotency import redis_client
from app.models import User

FREE_TIER = "free"
PRO_TIER = "pro"
PREMIUM_TIER = "premium"

FREE_DAILY_DECISION_LIMIT = 10
PRO_MONTHLY_TOKEN_LIMIT = int(os.getenv("PRO_MONTHLY_TOKEN_LIMIT", "100000"))
PREMIUM_MONTHLY_TOKEN_LIMIT = int(os.getenv("PREMIUM_MONTHLY_TOKEN_LIMIT", "500000"))

FREE_MODEL = "gpt-5.4-mini"
PRO_MODEL = "gpt-5.4-mini"
PREMIUM_MODEL = "gpt-5.4"


def get_user_tier(user: User | None) -> str:
    if not user:
        return FREE_TIER

    plan = (user.plan or "").strip().lower()
    if plan == PREMIUM_TIER and user.is_premium:
        return PREMIUM_TIER
    if plan == PRO_TIER and user.is_premium:
        return PRO_TIER
    return FREE_TIER


def get_model_for_user(user: User | None) -> str:
    tier = get_user_tier(user)
    if tier == PREMIUM_TIER:
        return PREMIUM_MODEL
    if tier == PRO_TIER:
        return PRO_MODEL
    return FREE_MODEL


def _daily_usage_key(user_id: int) -> str:
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"decision_usage:{user_id}:{today_utc}"


def _seconds_until_utc_midnight() -> int:
    now = datetime.now(timezone.utc)
    next_midnight = datetime.combine(
        (now + timedelta(days=1)).date(),
        datetime.min.time(),
        tzinfo=timezone.utc
    )
    return max(int((next_midnight - now).total_seconds()), 1)


def _monthly_token_usage_key(user_id: int) -> str:
    month_utc = datetime.now(timezone.utc).strftime("%Y-%m")
    return f"decision_tokens:{user_id}:{month_utc}"


def _seconds_until_next_utc_month() -> int:
    now = datetime.now(timezone.utc)
    if now.month == 12:
        next_month = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        next_month = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    return max(int((next_month - now).total_seconds()), 1)


def get_remaining_decisions(user: User | None) -> int | None:
    tier = get_user_tier(user)
    if tier in {PRO_TIER, PREMIUM_TIER}:
        return None

    if not user:
        return FREE_DAILY_DECISION_LIMIT

    current_count = redis_client.get(_daily_usage_key(user.id))
    used = int(current_count or 0)
    return max(FREE_DAILY_DECISION_LIMIT - used, 0)


def can_make_decision(user: User | None) -> bool:
    remaining = get_remaining_decisions(user)
    return remaining is None or remaining > 0


def record_decision_usage(user: User | None) -> None:
    if not user or get_user_tier(user) != FREE_TIER:
        return

    key = _daily_usage_key(user.id)
    count = redis_client.incr(key)
    if count == 1:
        redis_client.expire(key, _seconds_until_utc_midnight())


def get_monthly_token_limit(user: User | None) -> int | None:
    tier = get_user_tier(user)
    if tier == PRO_TIER:
        return PRO_MONTHLY_TOKEN_LIMIT
    if tier == PREMIUM_TIER:
        return PREMIUM_MONTHLY_TOKEN_LIMIT
    return None


def get_monthly_tokens_used(user: User | None) -> int:
    if not user:
        return 0
    current_count = redis_client.get(_monthly_token_usage_key(user.id))
    return int(current_count or 0)


def get_remaining_monthly_tokens(user: User | None) -> int | None:
    limit = get_monthly_token_limit(user)
    if limit is None:
        return None
    used = get_monthly_tokens_used(user)
    return max(limit - used, 0)


def can_use_monthly_tokens(user: User | None) -> bool:
    remaining = get_remaining_monthly_tokens(user)
    return remaining is None or remaining > 0


def record_monthly_token_usage(user: User | None, tokens_used: int) -> None:
    if not user or tokens_used <= 0:
        return

    if get_user_tier(user) not in {PRO_TIER, PREMIUM_TIER}:
        return

    key = _monthly_token_usage_key(user.id)
    count = redis_client.incrby(key, tokens_used)
    if count == tokens_used:
        redis_client.expire(key, _seconds_until_next_utc_month())
