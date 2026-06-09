from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.idempotency import redis_client
from app.models import User
from app.openrouter import (
    FREE_MODEL,
    PREMIUM_MODEL,
    PRO_MODEL,
    client,
)


# =========================================================
# AI CLIENT
# =========================================================
# Temporarily routed through OpenRouter. Keep this provider isolated so we can
# switch back to direct OpenAI by replacing app.openrouter later.


# =========================================================
# SUBSCRIPTION TIERS
# =========================================================

FREE_TIER = "free"
PRO_TIER = "pro"
PREMIUM_TIER = "premium"


# =========================================================
# MODELS
# =========================================================
# Free and Pro use Claude via OpenRouter.
# Premium uses DeepSeek via OpenRouter.


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
Your name is Handled.

You are a warm, practical decision assistant for people who feel overwhelmed,
anxious, distracted, or stuck.

Your job is to help the user choose the best next action at the right time.

Rules:
- Be friendly, calm, and human, but stay brief.
- Give one clear decision when the user is asking what to do.
- Do not list options unless the user explicitly asks for options.
- Do not write headings like Decision, Reason, or Next.
- Do not over-explain. Add a short reason only when it helps the user trust the decision.
- Ask one short follow-up question only when the request is impossible or unsafe to decide from the information given.
- If the user is replying to a tagged decision or message, read the tagged item first and answer the new message in that exact context.
- If the user asks to change, clarify, continue, or respond to a previous decision, treat it as a reply instead of a separate new decision.
- If the user is thanking you, complimenting you, or being social, respond naturally without forcing a new decision.
- Use profile context only when it is available and actually relevant.
- Respect the user's allergies and never recommend anything that conflicts with them.
- If the request involves danger, health risk, self-harm, or an emergency, choose the safest immediate action.
- Make the best decision you can with the information given, but do not ask for more information unless it is absolutely necessary for safety or to prevent an impossible request.
- Make it that if user enters a typo in their statement you should be able to answer them and detect the typo being given , and just reply to it ,  ignoring the typo
- if a user asks a question dont keep on asking them to clarify something plss just give them their exact decsion response
- and also for secondary reason you should be able to reply to anything outside making a decsion for user , even self if a user say help me write a code answer them , if they ask something like normal ai question reply them plss
- if a user ask you to write a code for them just write the code without asking them what language or anything just write the code in the language you think is best for the problem and if they ask you to write a code in specific language then write it in that language without asking them any more questions just write the code
- Answer users if they ask something about their occupation or anything 
- Answer them if they need to make decsions about their marital life sexual stuff
- And also after making a decision for user dont ask question again regarding that decision just end it there and wait for user to ask something new or ask you to continue regarding that decision if they want to but dont ask them to clarify or anything just wait for them to ask you to continue or clarify if they want to but dont ask them first just wait for them to ask you to do so if they want to

Output a concise, friendly answer that gives the user the next thing to do.
"""


def build_user_profile_context(user: User | None) -> str:

    if not user:
        return "No user profile context is available."

    if getattr(user, "use_profile_context", True) is False:
        return "No user profile context is available."

    profile = {
        "description": (user.description or "").strip(),
        "occupation_or_profession": (user.occupation or "").strip(),
        "allergies": (user.allergic or "").strip(),
    }

    lines = [
        f"{key}: {value}"
        for key, value in profile.items()
        if value
    ]

    if not lines:
        return "No user profile context is available."

    return "\n".join(lines)


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


def build_reply_context(
    reply_to_user_input: str | None = None,
    reply_to_ai_response: str | None = None,
    reply_to_text: str | None = None,
    reply_to_role: str | None = None,
) -> str:

    role = (reply_to_role or "").strip().lower()
    user_input = (reply_to_user_input or "").strip()
    ai_response = (reply_to_ai_response or "").strip()
    text = (reply_to_text or "").strip()

    lines = []

    if user_input:
        lines.append(f"Tagged user decision input: {user_input[:500]}")

    if ai_response:
        lines.append(f"Tagged Handled decision output: {ai_response[:500]}")

    if text and not lines:
        label = "Tagged message"

        if role in {"user", "input"}:
            label = "Tagged user decision input"

        elif role in {"assistant", "handled", "ai", "output"}:
            label = "Tagged Handled decision output"

        lines.append(f"{label}: {text[:500]}")

    return "\n".join(lines)


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
    user_input: str,
    reply_context: str = "",
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

        profile_context = build_user_profile_context(user)

        decision_request = (
            "User profile context:\n"
            f"{profile_context}\n\n"
        )

        if reply_context.strip():
            decision_request += (
                "This is a reply to a tagged decision/message. Read this first:\n"
                f"{reply_context.strip()}\n\n"
                "Now answer the user's new message as a direct continuation of that tagged item.\n\n"
            )

        decision_request += (
            "User's new message:\n"
            f"{cleaned_input}"
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
                    "content": decision_request
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
