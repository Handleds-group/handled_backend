import os
from dotenv import load_dotenv
import stripe

load_dotenv()

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
if not STRIPE_SECRET_KEY:
    raise RuntimeError("STRIPE_SECRET_KEY is not set in environment")

STRIPE_SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL")
STRIPE_CANCEL_URL = os.getenv("STRIPE_CANCEL_URL")

PRICE_IDS = {
    "pro": "price_1TFHRhJlP5JNMWILrC1RwRpt",
    "premium": "price_1TFGmSJlP5JNMWILEczZECIc",
}

stripe.api_key = STRIPE_SECRET_KEY

def create_checkout_session(
    user_id: str,
    plan: str,
    email: str,
    success_url: str | None = None,
    cancel_url: str | None = None,
) -> str:
    plan_key = plan.strip().lower()
    if plan_key not in PRICE_IDS:
        raise ValueError("Invalid plan. Use 'pro' or 'premium'.")
    email_value = (email or "").strip().lower()
    if not email_value:
        raise ValueError("A valid email is required for checkout.")
    resolved_success_url = success_url or STRIPE_SUCCESS_URL
    resolved_cancel_url = cancel_url or STRIPE_CANCEL_URL
    if not resolved_success_url or not resolved_cancel_url:
        raise ValueError("Stripe success and cancel URLs are not configured.")

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": PRICE_IDS[plan_key], "quantity": 1}],
        customer_email=email_value,
        success_url=resolved_success_url,
        cancel_url=resolved_cancel_url,
        metadata={
            "user_id": str(user_id),
            "plan": plan_key,
        },
        subscription_data={
            "metadata": {
                "user_id": str(user_id),
                "plan": plan_key,
            }
        },
    )
    return session.url


def cancel_subscription(subscription_id: str) -> None:
    if not subscription_id:
        return

    subscription = stripe.Subscription.retrieve(subscription_id)
    if subscription.get("status") == "canceled":
        return

    stripe.Subscription.delete(subscription_id)
