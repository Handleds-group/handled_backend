import datetime
import logging
import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
import stripe

from app.database import SessionLocal
from app.models import User, PaymentTransaction
from app.schemas import PaymentCheckoutRequest, PaymentCheckoutResponse, PaymentSessionVerifyResponse
from app.stripe_service import create_checkout_session
from app.email_utils import payment_receipt_email_html, payment_success_email_html, send_email_with_error

logger = logging.getLogger(__name__)

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
if not STRIPE_WEBHOOK_SECRET:
    raise RuntimeError("STRIPE_WEBHOOK_SECRET is not set in environment")

router = APIRouter()

PUBLIC_BACKEND_URL = os.getenv("PUBLIC_BACKEND_URL")


def _get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    try:
        user_int = int(user_id)
    except (TypeError, ValueError):
        return None
    result = db.execute(select(User).where(User.id == user_int))
    return result.scalars().first()


def _clear_subscription(db: Session, user: User):
    user.is_premium = False
    user.plan = None
    user.subscription_id = None
    db.add(user)
    db.commit()


def _build_absolute_url(request: Request, path: str) -> str:
    if PUBLIC_BACKEND_URL:
        return f"{PUBLIC_BACKEND_URL.rstrip('/')}{path}"

    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    if forwarded_proto and forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}{path}"

    host = request.headers.get("host") or ""
    if host and "localhost" not in host and "127.0.0.1" not in host:
        return f"{request.url.scheme}://{host}{path}"

    base = request.base_url
    return f"{str(base).rstrip('/')}{path}"


def _normalize_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    normalized = email.strip().lower()
    return normalized or None


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


def _has_active_subscription(user: User) -> bool:
    if not user.is_premium or not user.plan or not user.subscription_id:
        return False

    try:
        subscription = stripe.Subscription.retrieve(user.subscription_id)
    except Exception:
        logger.exception("Failed to retrieve Stripe subscription for user_id=%s", user.id)
        return True

    status = subscription.get("status")
    cancel_at_period_end = bool(subscription.get("cancel_at_period_end"))
    current_period_end = subscription.get("current_period_end")
    now_ts = int(datetime.datetime.utcnow().timestamp())

    if status in {"active", "trialing", "past_due", "unpaid"}:
        if current_period_end and current_period_end > now_ts:
            return True
        if status in {"active", "trialing"} and not current_period_end:
            return True

    if cancel_at_period_end and current_period_end and current_period_end > now_ts:
        return True

    return False


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


def _process_checkout_completion(
    *,
    db: Session,
    session_object: dict,
):
    metadata = session_object.get("metadata", {})
    user_id = metadata.get("user_id")
    plan = metadata.get("plan")
    subscription_id = session_object.get("subscription")
    customer_details = session_object.get("customer_details") or {}
    customer_email = session_object.get("customer_email") or customer_details.get("email")
    amount = session_object.get("amount_total")
    currency = session_object.get("currency")
    reference = session_object.get("id")
    status = session_object.get("payment_status") or "completed"
    created_ts = session_object.get("created")
    purchased_at = None
    if created_ts:
        purchased_at = datetime.datetime.utcfromtimestamp(created_ts).strftime("%Y-%m-%d %H:%M:%S UTC")

    logger.info(
        "Processing checkout completion for user_id=%s plan=%s subscription_id=%s reference=%s",
        user_id,
        plan,
        subscription_id,
        reference,
    )

    if user_id and plan:
        _set_subscription(db, user_id, plan, subscription_id, is_premium=True)

    _record_transaction(
        db=db,
        user_id=user_id,
        plan=plan,
        amount=amount,
        currency=currency,
        status=status,
        reference=reference,
    )
    _send_payment_success_email(
        db=db,
        user_id=user_id,
        fallback_email=customer_email,
        plan=plan,
    )
    _send_payment_receipt(
        db=db,
        user_id=user_id,
        fallback_email=customer_email,
        plan=plan,
        amount=amount,
        currency=currency,
        status=status,
        reference=reference,
        purchased_at=purchased_at,
    )


def _send_payment_receipt(
    *,
    db: Session,
    user_id: Optional[str],
    fallback_email: Optional[str],
    plan: Optional[str],
    amount: Optional[int],
    currency: Optional[str],
    status: Optional[str],
    reference: Optional[str],
    payment_method: Optional[str] = None,
    purchased_at: Optional[str] = None,
    billing_reason: Optional[str] = None,
):
    email_to = _normalize_email(fallback_email)
    if user_id:
        user = _get_user_by_id(db, user_id)
        if user and user.email:
            email_to = _normalize_email(user.email)

    if not email_to:
        logger.warning("Skipping payment receipt email because recipient email is missing for user_id=%s reference=%s", user_id, reference)
        return

    plan_label = (plan or "subscription").capitalize()
    subject = f"Handled payment receipt - {plan_label}"
    body = payment_receipt_email_html(
        plan=plan or "subscription",
        amount=amount,
        currency=currency,
        status=status or "completed",
        reference=reference,
        payment_method=payment_method,
        purchased_at=purchased_at,
        billing_reason=billing_reason,
    )
    success, error = send_email_with_error(subject=subject, email_to=email_to, body=body)
    if success:
        logger.info("Payment receipt email sent to %s for reference=%s", email_to, reference)
    else:
        logger.error("Failed to send payment receipt email to %s for reference=%s: %s", email_to, reference, error)


def _send_payment_success_email(
    *,
    db: Session,
    user_id: Optional[str],
    fallback_email: Optional[str],
    plan: Optional[str],
):
    email_to = _normalize_email(fallback_email)
    if user_id:
        user = _get_user_by_id(db, user_id)
        if user and user.email:
            email_to = _normalize_email(user.email)

    if not email_to:
        logger.warning("Skipping payment success email because recipient email is missing for user_id=%s", user_id)
        return

    plan_name = (plan or "subscription").capitalize()
    subject = f"Your Handled {plan_name} plan is active"
    body = payment_success_email_html(plan or "subscription")
    success, error = send_email_with_error(subject=subject, email_to=email_to, body=body)
    if success:
        logger.info("Payment success email sent to %s for user_id=%s", email_to, user_id)
    else:
        logger.error("Failed to send payment success email to %s for user_id=%s: %s", email_to, user_id, error)


@router.post("/create-checkout", response_model=PaymentCheckoutResponse)
def create_checkout(payload: PaymentCheckoutRequest, request: Request):
    db = SessionLocal()
    try:
        user = _get_user_by_id(db, payload.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if _has_active_subscription(user):
            raise HTTPException(
                status_code=400,
                detail="You already have an active subscription. You can make another payment only after it expires or is canceled."
            )

        if user.is_premium or user.plan or user.subscription_id:
            _clear_subscription(db, user)

        checkout_email = _normalize_email(user.email) or _normalize_email(payload.email)
        if not checkout_email:
            raise HTTPException(status_code=400, detail="A valid email is required to start checkout.")
        success_url = _build_absolute_url(request, "/success") + "?session_id={CHECKOUT_SESSION_ID}"
        cancel_url = _build_absolute_url(request, "/cancel")

        checkout_url = create_checkout_session(
            user_id=payload.user_id,
            plan=payload.plan,
            email=checkout_email,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create checkout session: {exc}") from exc
    finally:
        db.close()
    return PaymentCheckoutResponse(checkout_url=checkout_url)


@router.get("/verify-session", response_model=PaymentSessionVerifyResponse)
def verify_checkout_session(session_id: str):
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    db = SessionLocal()
    try:
        session_object = stripe.checkout.Session.retrieve(session_id)
        if not session_object:
            raise HTTPException(status_code=404, detail="Checkout session not found")

        payment_status = session_object.get("payment_status")
        if payment_status not in {"paid", "no_payment_required"}:
            return PaymentSessionVerifyResponse(
                status="pending",
                payment_status=payment_status,
                reference=session_object.get("id"),
                plan=(session_object.get("metadata") or {}).get("plan"),
                subscription_id=session_object.get("subscription"),
            )

        _process_checkout_completion(db=db, session_object=session_object)
        return PaymentSessionVerifyResponse(
            status="completed",
            payment_status=payment_status,
            reference=session_object.get("id"),
            plan=(session_object.get("metadata") or {}).get("plan"),
            subscription_id=session_object.get("subscription"),
        )
    except stripe.error.StripeError as exc:
        raise HTTPException(status_code=502, detail=f"Stripe verify failed: {exc.user_message or str(exc)}") from exc
    finally:
        db.close()


@router.post("/webhook")
async def stripe_webhook(request: Request):
    logger.info("Stripe webhook hit")
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    if not sig_header:
        logger.warning("Stripe webhook missing signature header")
        raise HTTPException(status_code=400, detail="Missing Stripe signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError as exc:
        logger.warning("Stripe webhook signature verification failed")
        raise HTTPException(status_code=400, detail="Invalid Stripe signature") from exc
    except Exception as exc:
        logger.exception("Stripe webhook payload parsing failed")
        raise HTTPException(status_code=400, detail="Invalid payload") from exc

    event_type = event["type"]
    data_object = event["data"]["object"]
    logger.info("Stripe event received: %s", event_type)

    db = SessionLocal()
    try:
        if event_type == "checkout.session.completed":
            _process_checkout_completion(db=db, session_object=data_object)

        elif event_type == "invoice.payment_succeeded":
            subscription_id = data_object.get("subscription")
            billing_reason = data_object.get("billing_reason")
            plan = None
            user_id = None
            customer_email = data_object.get("customer_email")
            if subscription_id:
                subscription = stripe.Subscription.retrieve(subscription_id)
                metadata = subscription.get("metadata", {})
                plan = metadata.get("plan")
                user_id = metadata.get("user_id")
            logger.info(
                "Processing invoice.payment_succeeded for user_id=%s plan=%s subscription_id=%s billing_reason=%s",
                user_id,
                plan,
                subscription_id,
                billing_reason,
            )
            amount = data_object.get("amount_paid")
            currency = data_object.get("currency")
            reference = data_object.get("id")
            status = data_object.get("status") or "succeeded"
            payment_method = None
            purchased_at = None
            created_ts = data_object.get("created")
            if created_ts:
                purchased_at = datetime.datetime.utcfromtimestamp(created_ts).strftime("%Y-%m-%d %H:%M:%S UTC")
            charge_id = data_object.get("charge")
            if charge_id:
                try:
                    charge = stripe.Charge.retrieve(charge_id)
                    payment_method_details = charge.get("payment_method_details") or {}
                    card_details = payment_method_details.get("card") or {}
                    brand = card_details.get("brand")
                    last4 = card_details.get("last4")
                    if brand and last4:
                        payment_method = f"{brand.title()} ending in {last4}"
                    elif brand:
                        payment_method = brand.title()
                except Exception:
                    logger.exception("Failed to retrieve charge details for receipt email reference=%s", reference)

            if user_id and plan:
                _set_subscription(db, user_id, plan, subscription_id, is_premium=True)
            _record_transaction(
                db=db,
                user_id=user_id,
                plan=plan,
                amount=amount,
                currency=currency,
                status=status,
                reference=reference,
            )
            _send_payment_receipt(
                db=db,
                user_id=user_id,
                fallback_email=customer_email,
                plan=plan,
                amount=amount,
                currency=currency,
                status=status,
                reference=reference,
                payment_method=payment_method,
                purchased_at=purchased_at,
                billing_reason=billing_reason,
            )

        elif event_type == "invoice.payment_failed":
            logger.warning("Invoice payment failed: %s", data_object.get("id"))

        elif event_type == "customer.subscription.deleted":
            subscription_id = data_object.get("id")
            metadata = data_object.get("metadata", {})
            user_id = metadata.get("user_id")
            logger.info(
                "Processing customer.subscription.deleted for user_id=%s subscription_id=%s",
                user_id,
                subscription_id,
            )
            if user_id:
                _set_subscription(db, user_id, None, None, is_premium=False)
            logger.info("Subscription deleted: %s", subscription_id)

        else:
            logger.info("Unhandled Stripe event: %s", event_type)
    finally:
        db.close()

    logger.info("Stripe webhook processed successfully: %s", event_type)
    return {"status": "ok"}
