import os
from datetime import datetime, timedelta, timezone

from openai import OpenAI

from app.idempotency import redis_client
from app.models import User


# =========================================================
# OPENAI CLIENT
# =========================================================

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


# =========================================================
# SUBSCRIPTION TIERS
# =========================================================

FREE_TIER = "free"
PRO_TIER = "pro"
PREMIUM_TIER = "premium"


# =========================================================
# MODELS
# =========================================================
# ONLY PREMIUM USES GPT-4o
# This massively protects your billing.

FREE_MODEL = "gpt-4o-mini"
PRO_MODEL = "gpt-4o-mini"
PREMIUM_MODEL = "gpt-4o"


# =========================================================
# REQUEST LIMITS
# =========================================================
# VERY IMPORTANT FOR COST CONTROL

FREE_DAILY_LIMIT = 10

PRO_MONTHLY_LIMIT = 2500

PREMIUM_MONTHLY_LIMIT = 6000


# =========================================================
# COOLDOWNS
# =========================================================
# Prevents spam requests and API abuse.

FREE_COOLDOWN_SECONDS = 60
PRO_COOLDOWN_SECONDS = 15
PREMIUM_COOLDOWN_SECONDS = 5


# =========================================================
# INPUT LIMITS
# =========================================================
# HUGE BILLING PROTECTION.
# Prevents giant prompts.

FREE_INPUT_LIMIT = 300
PRO_INPUT_LIMIT = 700
PREMIUM_INPUT_LIMIT = 1500


# =========================================================
# OUTPUT LIMITS
# =========================================================
# VERY IMPORTANT.
# Keep AI responses tiny and cheap.

FREE_MAX_TOKENS = 70
PRO_MAX_TOKENS = 90
PREMIUM_MAX_TOKENS = 120


# =========================================================
# SYSTEM PROMPT
# =========================================================
# SHORT PROMPT = LOWER COST

SYSTEM_PROMPT = """
You are Handled AI.

Your job is to make ONE clear decision for overwhelmed users.

Rules:
- Never give multiple options
- Never say "it depends"
- Never overexplain
- Be calm and confident
- Reduce overthinking
- Give one direct action
- Keep responses extremely short
- Speak simply for ADHD and anxious users
- No essays
- No long motivation

Format:

Decision:
<one direct decision>

Reason:
<one short reason>

Next:
<one immediate action>
"""


# =========================================================
# USER TIER LOGIC
# =========================================================

def get_user_tier(user: User | None) -> str:

    if not user:
        return FREE_TIER

    plan = (user.plan or "").strip().lower()

    if plan == PREMIUM_TIER and user.is_premium:
        return PREMIUM_TIER

    if plan == PRO_TIER and user.is_premium:
        return PRO_TIER

    return FREE_TIER


# =========================================================
# MODEL SELECTION
# =========================================================

def get_model_for_user(user: User | None) -> str:

    tier = get_user_tier(user)

    if tier == PREMIUM_TIER:
        return PREMIUM_MODEL

    if tier == PRO_TIER:
        return PRO_MODEL

    return FREE_MODEL


# =========================================================
# TOKEN LIMITS
# =========================================================

def get_max_tokens_for_user(user: User | None) -> int:

    tier = get_user_tier(user)

    if tier == PREMIUM_TIER:
        return PREMIUM_MAX_TOKENS

    if tier == PRO_TIER:
        return PRO_MAX_TOKENS

    return FREE_MAX_TOKENS


# =========================================================
# INPUT LIMITS
# =========================================================

def limit_input_by_user(user: User | None, text: str) -> str:

    tier = get_user_tier(user)

    cleaned = text.strip()

    if tier == PREMIUM_TIER:
        return cleaned[:PREMIUM_INPUT_LIMIT]

    if tier == PRO_TIER:
        return cleaned[:PRO_INPUT_LIMIT]

    return cleaned[:FREE_INPUT_LIMIT]


# =========================================================
# DAILY USAGE KEYS
# =========================================================

def _daily_usage_key(user_id: int) -> str:

    today_utc = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d")

    return f"decision_usage:{user_id}:{today_utc}"


def _seconds_until_utc_midnight() -> int:

    now = datetime.now(timezone.utc)

    next_midnight = datetime.combine(
        (now + timedelta(days=1)).date(),
        datetime.min.time(),
        tzinfo=timezone.utc
    )

    return max(
        int((next_midnight - now).total_seconds()),
        1
    )


# =========================================================
# MONTHLY USAGE KEYS
# =========================================================

def _monthly_usage_key(user_id: int) -> str:

    month_utc = datetime.now(
        timezone.utc
    ).strftime("%Y-%m")

    return f"decision_monthly:{user_id}:{month_utc}"


def _seconds_until_next_utc_month() -> int:

    now = datetime.now(timezone.utc)

    if now.month == 12:
        next_month = datetime(
            now.year + 1,
            1,
            1,
            tzinfo=timezone.utc
        )
    else:
        next_month = datetime(
            now.year,
            now.month + 1,
            1,
            tzinfo=timezone.utc
        )

    return max(
        int((next_month - now).total_seconds()),
        1
    )


# =========================================================
# COOLDOWN KEYS
# =========================================================

def _cooldown_key(user_id: int) -> str:
    return f"decision_cooldown:{user_id}"


# =========================================================
# COOLDOWN CHECK
# =========================================================

def can_make_request(user: User | None) -> bool:

    if not user:
        return True

    cooldown_exists = redis_client.exists(
        _cooldown_key(user.id)
    )

    return not cooldown_exists


def start_cooldown(user: User | None):

    if not user:
        return

    tier = get_user_tier(user)

    seconds = FREE_COOLDOWN_SECONDS

    if tier == PRO_TIER:
        seconds = PRO_COOLDOWN_SECONDS

    elif tier == PREMIUM_TIER:
        seconds = PREMIUM_COOLDOWN_SECONDS

    redis_client.setex(
        _cooldown_key(user.id),
        seconds,
        "1"
    )


# =========================================================
# REMAINING REQUESTS
# =========================================================

def get_remaining_requests(user: User | None):

    tier = get_user_tier(user)

    # FREE USERS
    if tier == FREE_TIER:

        if not user:
            return FREE_DAILY_LIMIT

        current = redis_client.get(
            _daily_usage_key(user.id)
        )

        used = int(current or 0)

        return max(
            FREE_DAILY_LIMIT - used,
            0
        )

    # PRO USERS
    if tier == PRO_TIER:

        assert user is not None

        current = redis_client.get(
            _monthly_usage_key(user.id)
        )

        used = int(current or 0)

        return max(
            PRO_MONTHLY_LIMIT - used,
            0
        )

    # PREMIUM USERS

    assert user is not None

    current = redis_client.get(
        _monthly_usage_key(user.id)
    )

    used = int(current or 0)

    return max(
        PREMIUM_MONTHLY_LIMIT - used,
        0
    )


# =========================================================
# USAGE VALIDATION
# =========================================================

def can_generate_decision(user: User | None) -> bool:

    remaining = get_remaining_requests(user)

    return remaining > 0


# =========================================================
# RECORD USAGE
# =========================================================

def record_usage(user: User | None):

    if not user:
        return

    tier = get_user_tier(user)

    # FREE USERS
    if tier == FREE_TIER:

        key = _daily_usage_key(user.id)

        count = redis_client.incr(key)

        if count == 1:
            redis_client.expire(
                key,
                _seconds_until_utc_midnight()
            )

        return

    # PRO + PREMIUM
    key = _monthly_usage_key(user.id)

    count = redis_client.incr(key)

    if count == 1:
        redis_client.expire(
            key,
            _seconds_until_next_utc_month()
        )


# =========================================================
# AI DECISION GENERATION
# =========================================================

async def generate_decision(
    user: User | None,
    user_input: str
):

    try:

        # LIMIT CHECK
        if not can_generate_decision(user):

            return {
                "success": False,
                "response": (
                    "You have reached your decision limit."
                ),
                "tokens_used": 0
            }

        # COOLDOWN CHECK
        if not can_make_request(user):

            return {
                "success": False,
                "response": (
                    "Please wait a moment before "
                    "making another decision."
                ),
                "tokens_used": 0
            }

        # CLEAN INPUT
        cleaned_input = limit_input_by_user(
            user,
            user_input
        )

        # MODEL
        model = get_model_for_user(user)

        # OUTPUT LIMIT
        max_tokens = get_max_tokens_for_user(user)

        # OPENAI REQUEST
        response = client.chat.completions.create(

            model=model,

            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": cleaned_input
                }
            ],

            # LOWER = CHEAPER + MORE STABLE
            temperature=0.3,

            # VERY IMPORTANT COST CONTROL
            max_tokens=max_tokens,

            # Prevent hanging requests
            timeout=15
        )

        # RECORD USAGE
        record_usage(user)

        # START COOLDOWN
        start_cooldown(user)

        # OUTPUT
        output = (
            response
            .choices[0]
            .message
            .content
        )

        return {
            "success": True,
            "response": output,
            "tokens_used": (
                response.usage.total_tokens
                if response.usage
                else 0
            )
        }

    except Exception:

        return {
            "success": False,
            "response": (
                "Decision unavailable right now. "
                "Please try again shortly."
            ),
            "tokens_used": 0
        }