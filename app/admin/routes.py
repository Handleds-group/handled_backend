from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.pagination import paginate
from app.models import (
    User,
    BugReport,
    PaymentTransaction,
    Notification,
    Wallet,
    WithdrawalRequest,
    DecisionHistory,
)
from app.admin.dependencies import require_admin, verify_admin_password
from app.admin.schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminUserListOut,
    AdminUserProfileOut,
    BugReportAdminOut,
    PaymentTransactionOut,
    NotificationCreate,
    NotificationOut,
    BroadcastNotificationCreate,
    BroadcastNotificationResponse,
    UserDeleteRequest,
    PaymentSummaryByCurrency,
    WalletOut,
    WithdrawalCreate,
    WithdrawalOut,
)
from app.email_utils import send_email, account_deleted_with_reason_email_html, broadcast_notification_email_html
from app.admin_security import AdminSecurityManager
from app.tokens import create_access_token

router = APIRouter()

@router.post("/login", response_model=AdminLoginResponse)
def admin_login(payload: AdminLoginRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    
    # Check if IP is blocked
    if AdminSecurityManager.is_ip_blocked(client_ip):
        raise HTTPException(status_code=403, detail="Your IP address has been temporarily blocked due to multiple failed login attempts")
    
    # Verify password
    if not verify_admin_password(payload.password):
        attempts = AdminSecurityManager.record_failed_login(client_ip)
        if attempts >= 5:
            AdminSecurityManager.block_ip(client_ip, duration=900)
            raise HTTPException(status_code=403, detail="Too many failed login attempts. Your IP has been blocked for 15 minutes")
        raise HTTPException(status_code=401, detail=f"Invalid admin password (Attempt {attempts}/5)")
    
    # Reset attempts on successful login
    AdminSecurityManager.reset_login_attempts(client_ip)
    token = create_access_token({"admin": True})
    return AdminLoginResponse(access_token=token)

def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        if len(value) == 10:
            return datetime.fromisoformat(value + "T00:00:00")
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {value}")

def _ensure_wallet(db: Session, currency: str = "usd") -> Wallet:
    wallet = db.execute(select(Wallet)).scalars().first()
    if wallet:
        return wallet
    wallet = Wallet(balance=0, currency=currency)
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    return wallet

@router.get("/users", response_model=list[AdminUserListOut], dependencies=[Depends(require_admin)])
def admin_list_users(
    q: Optional[str] = None,
    is_premium: Optional[bool] = None,
    registered_from: Optional[str] = None,
    registered_to: Optional[str] = None,
    last_seen_from: Optional[str] = None,
    last_seen_to: Optional[str] = None,
    pagination: dict = Depends(paginate),
    db: Session = Depends(get_db),
):
    limit, offset = pagination["limit"], pagination["offset"]
    query = select(User)

    if q:
        like = f"%{q}%"
        query = query.where(or_(User.username.ilike(like), User.email.ilike(like)))
    if is_premium is not None:
        query = query.where(User.is_premium == is_premium)

    reg_from = _parse_date(registered_from)
    reg_to = _parse_date(registered_to)
    if reg_from:
        query = query.where(User.created_at >= reg_from)
    if reg_to:
        query = query.where(User.created_at <= reg_to)

    seen_from = _parse_date(last_seen_from)
    seen_to = _parse_date(last_seen_to)
    if seen_from:
        query = query.where(User.last_seen >= seen_from)
    if seen_to:
        query = query.where(User.last_seen <= seen_to)

    result = db.execute(query.limit(limit).offset(offset))
    users = result.scalars().all()
    return users

@router.get("/users/{user_id}/profile", response_model=AdminUserProfileOut, dependencies=[Depends(require_admin)])
def admin_user_profile(user_id: int, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.id == user_id)).scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    txns = db.execute(
        select(PaymentTransaction)
        .where(PaymentTransaction.user_id == user_id)
        .order_by(PaymentTransaction.created_at.desc())
        .limit(5)
    ).scalars().all()

    profile = AdminUserProfileOut.model_validate(user)
    profile.last_premium_transactions = [
        PaymentTransactionOut.model_validate(t) for t in txns
    ]
    return profile

@router.delete("/users/{user_id}", dependencies=[Depends(require_admin)])
def admin_delete_user(user_id: int, payload: Optional[UserDeleteRequest] = None, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.id == user_id)).scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Send deletion notification email before deletion
    if user.email:
        try:
            reason = payload.reason if payload else None
            custom_message = payload.custom_message if payload else None
            email_html = account_deleted_with_reason_email_html(reason=reason, custom_message=custom_message)
            send_email(
                subject="Your Handled Account Has Been Deleted",
                email_to=user.email,
                body=email_html
            )
        except Exception as e:
            print(f"Failed to send deletion email to {user.email}: {e}")

    # Delete all associated data
    db.query(DecisionHistory).filter(DecisionHistory.user_id == str(user_id)).delete()
    db.query(BugReport).filter(BugReport.user_id == user_id).delete()
    db.query(PaymentTransaction).filter(PaymentTransaction.user_id == user_id).delete()
    db.query(Notification).filter(Notification.user_id == user_id).delete()

    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully", "email_sent": user.email is not None}

@router.get("/users/{user_id}/bug-reports", response_model=list[BugReportAdminOut], dependencies=[Depends(require_admin)])
def admin_user_bug_reports(user_id: int, db: Session = Depends(get_db)):
    reports = db.execute(
        select(BugReport).where(BugReport.user_id == user_id).order_by(BugReport.created_at.desc())
    ).scalars().all()
    return reports

@router.get("/bug-reports", response_model=list[BugReportAdminOut], dependencies=[Depends(require_admin)])
def admin_all_bug_reports(
    pagination: dict = Depends(paginate),
    db: Session = Depends(get_db),
):
    limit, offset = pagination["limit"], pagination["offset"]
    reports = db.execute(
        select(BugReport).order_by(BugReport.created_at.desc()).limit(limit).offset(offset)
    ).scalars().all()
    return reports

@router.get("/payments/summary", response_model=list[PaymentSummaryByCurrency], dependencies=[Depends(require_admin)])
def admin_payments_summary(db: Session = Depends(get_db)):
    rows = db.execute(
        select(
            PaymentTransaction.currency,
            func.coalesce(func.sum(PaymentTransaction.amount), 0),
            func.count(PaymentTransaction.id),
        )
        .where(PaymentTransaction.status.in_(["completed", "succeeded"]))
        .group_by(PaymentTransaction.currency)
    ).all()
    summary = []
    for currency, total_amount, total_count in rows:
        summary.append(
            PaymentSummaryByCurrency(
                currency=currency,
                total_amount=int(total_amount),
                total_count=int(total_count),
            )
        )
    return summary

@router.get("/wallet", response_model=WalletOut, dependencies=[Depends(require_admin)])
def admin_wallet(db: Session = Depends(get_db)):
    wallet = _ensure_wallet(db)
    return wallet

@router.post("/wallet/collate", response_model=WalletOut, dependencies=[Depends(require_admin)])
def admin_wallet_collate(db: Session = Depends(get_db)):
    wallet = _ensure_wallet(db)
    total_in = db.execute(
        select(func.coalesce(func.sum(PaymentTransaction.amount), 0))
        .where(PaymentTransaction.status.in_(["completed", "succeeded"]))
    ).scalar_one()
    total_out = db.execute(
        select(func.coalesce(func.sum(WithdrawalRequest.amount), 0))
        .where(WithdrawalRequest.status.in_(["approved", "paid"]))
    ).scalar_one()
    wallet.balance = int(total_in) - int(total_out)
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    return wallet

@router.post("/withdrawals", response_model=WithdrawalOut, dependencies=[Depends(require_admin)])
def admin_withdraw(payload: WithdrawalCreate, db: Session = Depends(get_db)):
    wallet = _ensure_wallet(db, currency=(payload.currency or "usd"))
    currency = payload.currency or wallet.currency
    if wallet.balance < payload.amount:
        raise HTTPException(status_code=400, detail="Insufficient wallet balance")
    wallet.balance -= payload.amount
    req = WithdrawalRequest(
        amount=payload.amount,
        currency=currency,
        destination=payload.destination,
        status="pending",
    )
    db.add(wallet)
    db.add(req)
    db.commit()
    db.refresh(req)
    return req

@router.get("/withdrawals", response_model=list[WithdrawalOut], dependencies=[Depends(require_admin)])
def admin_withdrawals(
    pagination: dict = Depends(paginate),
    db: Session = Depends(get_db),
):
    limit, offset = pagination["limit"], pagination["offset"]
    reqs = db.execute(
        select(WithdrawalRequest).order_by(WithdrawalRequest.created_at.desc()).limit(limit).offset(offset)
    ).scalars().all()
    return reqs

@router.post("/notifications/send", response_model=NotificationOut, dependencies=[Depends(require_admin)])
def admin_send_notification(payload: NotificationCreate, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.id == payload.user_id)).scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    note = Notification(
        user_id=payload.user_id,
        title=payload.title,
        message=payload.message,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


# Broadcast notification to all users and send email
@router.post("/notifications/broadcast", response_model=BroadcastNotificationResponse, dependencies=[Depends(require_admin)])
def admin_broadcast_notification(payload: BroadcastNotificationCreate, db: Session = Depends(get_db)):
    users = db.execute(select(User)).scalars().all()
    recipients_count = 0
    failed_count = 0
    for user in users:
        # Create notification in DB
        note = Notification(
            user_id=user.id,
            title=payload.title,
            message=payload.message,
        )
        db.add(note)
        recipients_count += 1
        # Send email if enabled and user has email
        if payload.send_email and user.email:
            subject = payload.title
            body = broadcast_notification_email_html(payload.title, payload.message)
            try:
                if not send_email(subject, user.email, body):
                    failed_count += 1
            except Exception:
                failed_count += 1
    db.commit()
    return BroadcastNotificationResponse(
        success=True,
        message="Notification sent to all users.",
        recipients_count=recipients_count,
        failed_count=failed_count,
    )


# ==================== ADMIN SECURITY ENDPOINTS ====================

@router.get("/security/blocked-ips", dependencies=[Depends(require_admin)])
def get_blocked_ips():
    """Get list of currently blocked IPs"""
    stats = AdminSecurityManager.get_admin_stats()
    return stats


@router.post("/security/block-ip/{ip_address}", dependencies=[Depends(require_admin)])
def block_admin_ip(ip_address: str):
    """Manually block an IP address from admin access"""
    AdminSecurityManager.block_ip(ip_address, duration=3600)
    return {"message": f"IP {ip_address} has been blocked"}


@router.post("/security/unblock-ip/{ip_address}", dependencies=[Depends(require_admin)])
def unblock_admin_ip(ip_address: str):
    """Manually unblock an IP address"""
    AdminSecurityManager.unblock_ip(ip_address)
    return {"message": f"IP {ip_address} has been unblocked"}


@router.post("/security/rate-limit-check", dependencies=[Depends(require_admin)])
def check_rate_limit(request: Request):
    """Check current rate limit status"""
    client_ip = request.client.host if request.client else "unknown"
    is_allowed, remaining = AdminSecurityManager.check_admin_rate_limit(client_ip)
    return {
        "ip": client_ip,
        "is_allowed": is_allowed,
        "remaining_requests": remaining
    }

