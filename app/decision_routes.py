# decision_routes.py

from datetime import datetime
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import get_auth_db, get_supabase_db
from .decision_service import build_reply_context, build_user_profile_context, generate_decision
from .middleware import DecisionCacheMiddleware
from .models import DecisionHistory, DecisionUsageEvent, User
from .schemas import DecisionRequest, DecisionResponse, DeleteAllDecisionsRequest, DeleteAllDecisionsResponse
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
            pass
        else:
            db.add(
                DecisionUsageEvent(
                    user_id=user_id,
                    decision_id=decision.id,
                    created_at=decision.created_at or datetime.utcnow(),
                )
            )
            existing_decision_ids.add(decision.id)
            created_any = True

        for inline_decision in _get_inline_decisions(decision):
            inline_id = inline_decision.get("id")
            if not inline_id or inline_id in existing_decision_ids:
                continue
            db.add(
                DecisionUsageEvent(
                    user_id=user_id,
                    decision_id=inline_id,
                    created_at=_parse_inline_created_at(inline_decision.get("created_at")) or decision.created_at or datetime.utcnow(),
                )
            )
            existing_decision_ids.add(inline_id)
            created_any = True

    if created_any:
        db.commit()


def _get_inline_decisions(decision: DecisionHistory) -> list[dict]:
    inline_decisions = decision.inline_decisions or []
    return inline_decisions if isinstance(inline_decisions, list) else []


def _parse_inline_created_at(value) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _next_decision_number(user_id: str, db: Session) -> int:
    max_number = db.query(func.max(DecisionHistory.decision_number)) \
        .filter(DecisionHistory.user_id == user_id) \
        .scalar()
    if max_number:
        return int(max_number) + 1

    existing_roots = db.query(func.count(DecisionHistory.id)) \
        .filter(DecisionHistory.user_id == user_id) \
        .filter(DecisionHistory.parent_decision_id.is_(None)) \
        .scalar()
    return int(existing_roots or 0) + 1


def _find_decision_reference(
    user_id: str,
    decision_id: Optional[str],
    db: Session,
) -> tuple[Optional[DecisionHistory], Optional[str], Optional[str]]:
    if not decision_id:
        return None, None, None

    decision = db.query(DecisionHistory) \
        .filter(DecisionHistory.id == decision_id) \
        .filter(DecisionHistory.user_id == user_id) \
        .first()

    if decision:
        root = decision
        if decision.parent_decision_id:
            root = db.query(DecisionHistory) \
                .filter(DecisionHistory.id == decision.parent_decision_id) \
                .filter(DecisionHistory.user_id == user_id) \
                .first() or decision
        return root, decision.input_text, decision.ai_response

    roots = db.query(DecisionHistory) \
        .filter(DecisionHistory.user_id == user_id) \
        .all()
    for root in roots:
        for inline_decision in _get_inline_decisions(root):
            if inline_decision.get("id") == decision_id:
                return root, inline_decision.get("input_text"), inline_decision.get("ai_response")

    return None, None, None


def _history_item(decision: DecisionHistory) -> dict:
    return {
        "id": decision.id,
        "user_id": decision.user_id,
        "decision_number": decision.decision_number,
        "input_text": decision.input_text,
        "ai_response": decision.ai_response,
        "tokens_used": decision.tokens_used or 0,
        "inline_decisions": _get_inline_decisions(decision),
        "created_at": decision.created_at,
    }


def _inline_tokens(decision: DecisionHistory) -> int:
    return sum(
        int(inline_decision.get("tokens_used") or 0)
        for inline_decision in _get_inline_decisions(decision)
    )


def _root_only_tokens(decision: DecisionHistory) -> int:
    return max(int(decision.tokens_used or 0) - _inline_tokens(decision), 0)


def _decision_total(decision: DecisionHistory) -> int:
    return 1 + len(_get_inline_decisions(decision))


def _usage_ids_for_decision(decision: DecisionHistory) -> list[str]:
    ids = [decision.id]
    ids.extend(
        inline_decision["id"]
        for inline_decision in _get_inline_decisions(decision)
        if inline_decision.get("id")
    )
    return ids


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
    root_decision = None

    if payload.reply_to_decision_id:
        root_decision, stored_user_input, stored_ai_response = _find_decision_reference(
            payload.user_id,
            payload.reply_to_decision_id,
            supabase_db,
        )
        if not root_decision:
            raise HTTPException(status_code=404, detail="Reply decision not found")
        if root_decision:
            reply_to_user_input = reply_to_user_input or stored_user_input
            reply_to_ai_response = reply_to_ai_response or stored_ai_response

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
    is_inline = root_decision is not None

    if is_inline:
        inline_decisions = [*_get_inline_decisions(root_decision)]
        inline_decisions.append(
            {
                "id": decision_id,
                "root_decision_id": root_decision.id,
                "decision_number": root_decision.decision_number,
                "input_text": user_input,
                "ai_response": ai_response,
                "tokens_used": actual_tokens_used,
                "reply_to_decision_id": payload.reply_to_decision_id,
                "reply_to_user_input": reply_to_user_input,
                "reply_to_ai_response": reply_to_ai_response,
                "reply_to_text": payload.reply_to_text,
                "reply_to_role": payload.reply_to_role,
                "created_at": created_at.isoformat(),
            }
        )
        root_decision.inline_decisions = inline_decisions
        root_decision.tokens_used = (root_decision.tokens_used or 0) + actual_tokens_used
        supabase_db.add(root_decision)
    else:
        decision = DecisionHistory(
            id=decision_id,
            user_id=payload.user_id,
            decision_number=_next_decision_number(payload.user_id, supabase_db),
            input_text=user_input,
            ai_response=ai_response,
            tokens_used=actual_tokens_used,
            inline_decisions=[],
            created_at=created_at
        )
        root_decision = decision
        supabase_db.add(decision)

    usage_event = DecisionUsageEvent(
        user_id=payload.user_id,
        decision_id=decision_id,
        created_at=created_at,
    )

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
            "decision_id": decision_id,
            "root_decision_id": root_decision.id,
            "inline_decision_id": decision_id if is_inline else None,
            "decision_number": root_decision.decision_number,
            "is_inline": is_inline,
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
        .filter(DecisionHistory.parent_decision_id.is_(None)) \
        .order_by(DecisionHistory.created_at.desc()) \
        .all()

    return {
        "count": len(history),
        "total_decisions": sum(_decision_total(decision) for decision in history),
        "data": [_history_item(decision) for decision in history]
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


@router.delete("/history/{user_id}", response_model=DeleteAllDecisionsResponse)
async def delete_all_decisions(
    user_id: str,
    payload: Optional[DeleteAllDecisionsRequest] = None,
    db: Session = Depends(get_supabase_db),
):
    if payload and payload.user_id != user_id:
        raise HTTPException(status_code=400, detail="Payload user_id must match path user_id")
    if payload and not payload.confirm:
        raise HTTPException(status_code=400, detail="confirm must be true")

    decisions = db.query(DecisionHistory) \
        .filter(DecisionHistory.user_id == user_id) \
        .all()
    deleted_decisions = sum(_decision_total(decision) for decision in decisions)

    deleted_usage_events = db.query(DecisionUsageEvent) \
        .filter(DecisionUsageEvent.user_id == user_id) \
        .delete(synchronize_session=False)
    db.query(DecisionHistory) \
        .filter(DecisionHistory.user_id == user_id) \
        .delete(synchronize_session=False)
    db.commit()

    return {
        "message": "All decisions deleted successfully",
        "user_id": user_id,
        "deleted_decisions": deleted_decisions,
        "deleted_usage_events": deleted_usage_events,
    }


@router.delete("/{decision_id}")
async def delete_decision(decision_id: str, db: Session = Depends(get_supabase_db)):
    decision = db.query(DecisionHistory) \
        .filter(DecisionHistory.id == decision_id) \
        .first()

    if decision:
        ids_to_delete = _usage_ids_for_decision(decision)
        deleted_usage_events = db.query(DecisionUsageEvent) \
            .filter(DecisionUsageEvent.decision_id.in_(ids_to_delete)) \
            .delete(synchronize_session=False)
        db.delete(decision)
        db.commit()
        return {
            "message": "Deleted successfully",
            "deleted_decisions": len(ids_to_delete),
            "deleted_usage_events": deleted_usage_events,
        }

    roots = db.query(DecisionHistory).all()
    for root in roots:
        inline_decisions = _get_inline_decisions(root)
        remaining_inline_decisions = [
            inline_decision
            for inline_decision in inline_decisions
            if inline_decision.get("id") != decision_id
        ]
        if len(remaining_inline_decisions) == len(inline_decisions):
            continue

        root_tokens = _root_only_tokens(root)
        root.inline_decisions = remaining_inline_decisions
        root.tokens_used = root_tokens + sum(
            int(inline_decision.get("tokens_used") or 0)
            for inline_decision in remaining_inline_decisions
        )
        db.add(root)
        deleted_usage_events = db.query(DecisionUsageEvent) \
            .filter(DecisionUsageEvent.decision_id == decision_id) \
            .delete(synchronize_session=False)
        db.commit()
        return {
            "message": "Deleted successfully",
            "deleted_decisions": 1,
            "deleted_usage_events": deleted_usage_events,
        }

    raise HTTPException(status_code=404, detail="Decision not found")
