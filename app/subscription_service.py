from app.models import User

FREE_TIER = "free"
PRO_TIER = "pro"
PREMIUM_TIER = "premium"

FREE_MODEL = "gpt-4o-mini"
PRO_MODEL = "gpt-4o-mini"
PREMIUM_MODEL = "gpt-4o"


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
