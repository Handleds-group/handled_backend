# decision_routes.py

from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .decision_service import generate_decision
from .middleware import DecisionCacheMiddleware
from .models import DecisionHistory, User
from .schemas import DecisionRequest, DecisionResponse
from .subscription_service import can_make_decision, can_use_monthly_tokens, get_model_for_user, get_remaining_decisions, get_remaining_monthly_tokens, get_user_tier, record_decision_usage, record_monthly_token_usage

router = APIRouter(tags=["Decisions"])


@router.post("/make", response_model=DecisionResponse)
async def make_decision(payload: DecisionRequest, db: Session = Depends(get_db)):
    user_input = payload.user_input.strip()
    user = None

    if not user_input:
        raise HTTPException(status_code=400, detail="Input is required")

    try:
        user_id_int = int(payload.user_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid user_id")

    user = db.query(User).filter(User.id == user_id_int).first()
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
    cached_result = DecisionCacheMiddleware.get_cached_response(
        user_input=user_input,
        model=selected_model
    )

    if cached_result:
        ai_response = cached_result["response"]
        actual_tokens_used = 0
        cache_hit = True
    else:
        ai_result = await generate_decision(
            user_input=user_input,
            model=selected_model
        )
        ai_response = ai_result["response"]
        actual_tokens_used = ai_result["tokens_used"]
        DecisionCacheMiddleware.set_cached_response(
            user_input=user_input,
            model=selected_model,
            response_text=ai_response
        )
        cache_hit = False

    decision = DecisionHistory(
        id=str(uuid.uuid4()),
        user_id=payload.user_id,
        input_text=user_input,
        ai_response=ai_response,
        created_at=datetime.utcnow()
    )

    db.add(decision)
    db.commit()

    # Best-effort token usage tracking
    try:
        if user and actual_tokens_used > 0:
            user.tokens_used = (user.tokens_used or 0) + actual_tokens_used
            db.add(user)
            db.commit()
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
async def get_history(user_id: str, db: Session = Depends(get_db)):
    history = db.query(DecisionHistory) \
        .filter(DecisionHistory.user_id == user_id) \
        .order_by(DecisionHistory.created_at.desc()) \
        .all()

    return {
        "count": len(history),
        "data": history
    }


@router.delete("/{decision_id}")
async def delete_decision(decision_id: str, db: Session = Depends(get_db)):
    decision = db.query(DecisionHistory) \
        .filter(DecisionHistory.id == decision_id) \
        .first()

    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    db.delete(decision)
    db.commit()

    return {"message": "Deleted successfully"}
