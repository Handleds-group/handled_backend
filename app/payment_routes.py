import logging
import os
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
import stripe

from app.database import SessionLocal
from app.models import User, PaymentTransaction
from app.schemas import PaymentCheckoutRequest, PaymentCheckoutResponse
from app.stripe_service import create_checkout_session
from app.email_utils import send_email, send_email_with_error, payment_success_email_html

logger = logging.getLogger(__name__)

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
if not STRIPE_WEBHOOK_SECRET:
    raise RuntimeError("STRIPE_WEBHOOK_SECRET is not set in environment")

router = APIRouter()
EMAIL_DEBUG_ENABLED = os.getenv("EMAIL_DEBUG_ENABLED", "false").lower() == "true"

def _get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    try:
        user_int = int(user_id)
    except (TypeError, ValueError):
        return None
    result = db.execute(select(User).where(User.id == user_int))
    return result.scalars().first()

def _set_subscription(
    db: Session,
    user_id: str,
    plan: Optional[str],
    subscription_id: Optional[str],
    is_premium: bool,
):
    user = _get_user_by_id(db, user_id)
    if not user:
        logger.warning("Webhook user not found: %s", user_id)
        return
    user.is_premium = is_premium
    user.plan = plan
    user.subscription_id = subscription_id
    db.add(user)
    db.commit()

def _send_payment_email(email: str, plan: str):
    success = send_email(
        subject="Payment Successful",
        email_to=email,
        body=payment_success_email_html(plan),
    )
    if not success:
        logger.error("Failed to send payment email (SMTP error)")

def _record_transaction(
    db: Session,
    user_id: Optional[str],
    plan: Optional[str],
    amount: Optional[int],
    currency: Optional[str],
    status: str,
    reference: Optional[str],
):
    if amount is None:
        return
    user_id_int = None
    if user_id:
        try:
            user_id_int = int(user_id)
        except (TypeError, ValueError):
            user_id_int = None
    if reference:
        existing = db.execute(select(PaymentTransaction).where(PaymentTransaction.reference == reference)).scalars().first()
        if existing:
            return
    txn = PaymentTransaction(
        user_id=user_id_int,
        plan=plan,
        amount=amount,
        currency=currency or "usd",
        status=status,
        provider="stripe",
        reference=reference,
    )
    db.add(txn)
    db.commit()

@router.post("/create-checkout", response_model=PaymentCheckoutResponse)
def create_checkout(payload: PaymentCheckoutRequest):
    try:
        checkout_url = create_checkout_session(
            user_id=payload.user_id,
            plan=payload.plan,
            email=payload.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create checkout session: {exc}") from exc
    return PaymentCheckoutResponse(checkout_url=checkout_url)

@router.post("/webhook")
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid payload") from exc

    event_type = event["type"]
    data_object = event["data"]["object"]

    db = SessionLocal()
    try:
        if event_type == "checkout.session.completed":
            metadata = data_object.get("metadata", {})
            user_id = metadata.get("user_id")
            plan = metadata.get("plan")
            subscription_id = data_object.get("subscription")
            if user_id and plan:
                _set_subscription(db, user_id, plan, subscription_id, is_premium=True)
            _record_transaction(
                db=db,
                user_id=user_id,
                plan=plan,
                amount=data_object.get("amount_total"),
                currency=data_object.get("currency"),
                status="completed",
                reference=data_object.get("id"),
            )

            email = (
                data_object.get("customer_details", {}).get("email")
                or data_object.get("customer_email")
            )
            if email and plan:
                background_tasks.add_task(_send_payment_email, email, plan)

        elif event_type == "invoice.payment_succeeded":
            subscription_id = data_object.get("subscription")
            billing_reason = data_object.get("billing_reason")
            plan = None
            user_id = None
            if subscription_id:
                subscription = stripe.Subscription.retrieve(subscription_id)
                metadata = subscription.get("metadata", {})
                plan = metadata.get("plan")
                user_id = metadata.get("user_id")
            if user_id and plan:
                _set_subscription(db, user_id, plan, subscription_id, is_premium=True)
            _record_transaction(
                db=db,
                user_id=user_id,
                plan=plan,
                amount=data_object.get("amount_paid"),
                currency=data_object.get("currency"),
                status="succeeded",
                reference=data_object.get("id"),
            )

            if billing_reason == "subscription_create":
                email = data_object.get("customer_email")
                if email and plan:
                    background_tasks.add_task(_send_payment_email, email, plan)

        elif event_type == "invoice.payment_failed":
            logger.warning("Invoice payment failed: %s", data_object.get("id"))

        elif event_type == "customer.subscription.deleted":
            subscription_id = data_object.get("id")
            metadata = data_object.get("metadata", {})
            user_id = metadata.get("user_id")
            if user_id:
                _set_subscription(db, user_id, None, None, is_premium=False)
            logger.info("Subscription deleted: %s", subscription_id)

        else:
            logger.info("Unhandled Stripe event: %s", event_type)
    finally:
        db.close()

    return {"status": "ok"}

@router.get("/debug-email")
def debug_email(email: str):
    if not EMAIL_DEBUG_ENABLED:
        raise HTTPException(status_code=403, detail="Email debug is disabled")
    success, error = send_email_with_error(
        subject="Handled SMTP Debug",
        email_to=email,
        body=payment_success_email_html("pro"),
    )
    return {"success": success, "error": error}
