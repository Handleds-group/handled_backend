from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.auth import router as auth_router
from app.users import router as users_router
from app.health import router as health_router
from app.middleware import KillSwitchMiddleware, IdempotencyMiddleware, TimeoutMiddleware, RateLimitMiddleware
from app.database import init_db
from app.decision_routes import router as decision_router
from app.decision_service import generate_decision
from app.bug_reports import router as bug_reports_router
from app.payment_routes import router as payment_router
from app.web_pages import router as web_pages_router
from app.admin.routes import router as admin_router
from app.notifications import router as notifications_router

app = FastAPI(title="Handled Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(health_router, prefix="/health", tags=["Health"])
app.include_router(bug_reports_router, prefix="/bug-reports", tags=["Bug Reports"])
app.include_router(payment_router, prefix="/payments", tags=["Payments"])
app.include_router(web_pages_router, tags=["Pages"])
app.include_router(admin_router, prefix="/admin", tags=["Admin"])
app.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])

@app.on_event("startup")
def on_startup():
    init_db()

app.mount("/images", StaticFiles(directory="images"), name="images")

@app.get("/")
async def root():
    return {"message": "Handled backend running with KillSwitch, OTP, idempotency, and timeout!"}
