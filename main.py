from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from app.files import ensure_upload_dir
from app.auth import router as auth_router
from app.users import router as users_router
from app.history import router as history_router
from app.health import router as health_router
from app.middleware import KillSwitchMiddleware, IdempotencyMiddleware, TimeoutMiddleware, RateLimitMiddleware
from app.database import init_db
from app.decision_routes import router as decision_router
from app.decision_service import generate_decision
from app.bug_reports import router as bug_reports_router
from app.payment_routes import router as payment_router, stripe_webhook
from app.web_pages import router as web_pages_router

app = FastAPI(title="Handled Backend")

# Ensure uploads directory exists before mounting static files
ensure_upload_dir()

# --------------------------
# Middleware
# --------------------------
app.add_middleware(TimeoutMiddleware, timeout=20)     # Custom timeout
app.add_middleware(KillSwitchMiddleware)             # Kill switch for DB/Redis/Paystack
app.add_middleware(IdempotencyMiddleware)            # Idempotency for POST/PUT
app.add_middleware(RateLimitMiddleware, requests_per_minute=60)

# --------------------------
# Routers
# --------------------------
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(users_router, prefix="/users", tags=["Users"])
app.include_router(decision_router, prefix="/decisions", tags=["Decisions"])
app.include_router(history_router, prefix="/history", tags=["History"])
app.include_router(health_router, prefix="/health", tags=["Health"])
app.include_router(bug_reports_router, prefix="/bug-reports", tags=["Bug Reports"])
app.include_router(payment_router, prefix="/payments", tags=["Payments"])
app.include_router(web_pages_router, tags=["Pages"])

@app.on_event("startup")
def on_startup():
    ensure_upload_dir()
    init_db()

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/images", StaticFiles(directory="images"), name="images")

@app.get("/")
async def root():
    return {"message": "Handled backend running with KillSwitch, OTP, idempotency, and timeout!"}

@app.post("/webhook")
async def stripe_webhook_root(request: Request):
    return await stripe_webhook(request)
