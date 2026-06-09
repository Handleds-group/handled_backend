# decision_routes.py

from datetime import datetime
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .database import get_auth_db, get_supabase_db
from .decision_service import build_reply_context, build_user_profile_context, generate_decision
from .middleware import DecisionCacheMiddleware
from .models import DecisionHistory, DecisionUsageEvent, User
from .schemas import DecisionRequest, DecisionResponse
from .subscription_service import can_make_decision, can_use_monthly_tokens, get_model_for_user, get_remaining_decisions, get_remaining_monthly_tokens, get_user_tier, record_decision_usage, record_monthly_token_usage

router = APIRouter(tags=["Decisions"])

MONTH_LABELS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]


def _backfill_decision_usage_events(user_id: str, db: Session) -> None:
    existing_decision_ids = {
        row[0]
        for row in db.query(DecisionUsageEvent.decision_id)
        .filter(DecisionUsageEvent.user_id == user_id)
        .all()
    }

    history = db.query(DecisionHistory) \
        .filter(DecisionHistory.user_id == user_id) \
        .all()

    created_any = False

    for decision in history:
        if decision.id in existing_decision_ids:
            continue

        db.add(
            DecisionUsageEvent(
                user_id=user_id,
                decision_id=decision.id,
                created_at=decision.created_at or datetime.utcnow(),
            )
        )
        created_any = True

    if created_any:
        db.commit()


@router.post("/make", response_model=DecisionResponse)
async def make_decision(
    payload: DecisionRequest,
    auth_db: Session = Depends(get_auth_db),
    supabase_db: Session = Depends(get_supabase_db),
):
    user_input = payload.user_input.strip()
    user = None

    if not user_input:
        raise HTTPException(status_code=400, detail="Input is required")

    try:
        user_id_int = int(payload.user_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid user_id")

    user = auth_db.query(User).filter(User.id == user_id_int).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not can_make_decision(user):
        raise HTTPException(
            status_code=403,
            detail="Free tier users can make up to 10 decisions per day. Upgrade to Pro or Premium for unlimited decisions."
        )
    if not can_use_monthly_tokens(user):
        raise HTTPException(
            status_code=403,
            detail="You have reached your monthly token allocation for your current plan."
        )

    selected_model = get_model_for_user(user)
    profile_context = build_user_profile_context(user)

    reply_to_user_input = payload.reply_to_user_input
    reply_to_ai_response = payload.reply_to_ai_response

    if payload.reply_to_decision_id:
        replied_decision = supabase_db.query(DecisionHistory) \
            .filter(DecisionHistory.id == payload.reply_to_decision_id) \
            .filter(DecisionHistory.user_id == payload.user_id) \
            .first()

        if replied_decision:
            reply_to_user_input = reply_to_user_input or replied_decision.input_text
            reply_to_ai_response = reply_to_ai_response or replied_decision.ai_response

    reply_context = build_reply_context(
        reply_to_user_input=reply_to_user_input,
        reply_to_ai_response=reply_to_ai_response,
        reply_to_text=payload.reply_to_text,
        reply_to_role=payload.reply_to_role,
    )

    cached_result = DecisionCacheMiddleware.get_cached_response(
        user_input=user_input,
        model=selected_model,
        profile_context=profile_context,
        reply_context=reply_context,
    )

    if cached_result:
        ai_response = cached_result["response"]
        actual_tokens_used = 0
        cache_hit = True
    else:
        ai_result = await generate_decision(
            user=user,
            user_input=user_input,
            reply_context=reply_context,
        )
        ai_response = ai_result["response"]
        actual_tokens_used = ai_result["tokens_used"]
        DecisionCacheMiddleware.set_cached_response(
            user_input=user_input,
            model=selected_model,
            response_text=ai_response,
            profile_context=profile_context,
            reply_context=reply_context,
        )
        cache_hit = False

    decision_id = str(uuid.uuid4())
    created_at = datetime.utcnow()

    decision = DecisionHistory(
        id=decision_id,
        user_id=payload.user_id,
        input_text=user_input,
        ai_response=ai_response,
        tokens_used=actual_tokens_used,
        created_at=created_at
    )
    usage_event = DecisionUsageEvent(
        user_id=payload.user_id,
        decision_id=decision_id,
        created_at=created_at,
    )

    supabase_db.add(decision)
    supabase_db.add(usage_event)
    supabase_db.commit()

    # Update last seen
    try:
        user.last_seen = datetime.utcnow()
        auth_db.add(user)
        auth_db.commit()
    except Exception:
        pass

    # Best-effort token usage tracking
    try:
        if user and actual_tokens_used > 0:
            user.tokens_used = (user.tokens_used or 0) + actual_tokens_used
            auth_db.add(user)
            auth_db.commit()
    except Exception:
        pass

    try:
        record_decision_usage(user)
    except Exception:
        pass

    try:
        record_monthly_token_usage(user, actual_tokens_used)
    except Exception:
        pass

    return {
        "message": "Decision generated successfully",
        "data": {
            "decision_id": decision.id,
            "response": ai_response,
            "cached": cache_hit,
            "tier": get_user_tier(user),
            "remaining_decisions_today": get_remaining_decisions(user),
            "monthly_tokens_remaining": get_remaining_monthly_tokens(user)
        }
    }


@router.get("/history/{user_id}")
async def get_history(user_id: str, db: Session = Depends(get_supabase_db)):
    history = db.query(DecisionHistory) \
        .filter(DecisionHistory.user_id == user_id) \
        .order_by(DecisionHistory.created_at.desc()) \
        .all()

    return {
        "count": len(history),
        "data": history
    }


@router.get("/stats/{user_id}")
async def get_decision_stats(
    user_id: str,
    year: Optional[int] = Query(default=None, ge=1970, le=9999),
    auth_db: Session = Depends(get_auth_db),
    supabase_db: Session = Depends(get_supabase_db),
):
    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid user_id")

    user = auth_db.query(User).filter(User.id == user_id_int).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    selected_year = year or datetime.utcnow().year

    _backfill_decision_usage_events(user_id, supabase_db)

    account_created_at = user.created_at
    year_start = datetime(selected_year, 1, 1)
    year_end = datetime(selected_year + 1, 1, 1)

    year_events = supabase_db.query(DecisionUsageEvent.created_at) \
        .filter(DecisionUsageEvent.user_id == user_id) \
        .filter(DecisionUsageEvent.created_at >= year_start) \
        .filter(DecisionUsageEvent.created_at < year_end) \
        .all()

    all_events = supabase_db.query(DecisionUsageEvent.created_at) \
        .filter(DecisionUsageEvent.user_id == user_id) \
        .all()

    monthly_counts = {month: 0 for month in range(1, 13)}

    for event in year_events:
        created_at = event[0]
        if created_at:
            monthly_counts[created_at.month] += 1

    monthly = [
        {
            "month": month,
            "label": MONTH_LABELS[month - 1],
            "count": monthly_counts[month],
        }
        for month in range(1, 13)
    ]

    total_since_account_created = sum(
        1
        for event in all_events
        if event[0] and (not account_created_at or event[0] >= account_created_at.replace(tzinfo=None))
    )

    return {
        "user_id": user_id,
        "year": selected_year,
        "account_created_at": account_created_at,
        "total_since_account_created": total_since_account_created,
        "total_for_year": sum(monthly_counts.values()),
        "monthly": monthly,
    }


@router.delete("/{decision_id}")
async def delete_decision(decision_id: str, db: Session = Depends(get_supabase_db)):
    decision = db.query(DecisionHistory) \
        .filter(DecisionHistory.id == decision_id) \
        .first()

    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    db.delete(decision)
    db.commit()

    return {"message": "Deleted successfully"}
