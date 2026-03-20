from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.files import ensure_upload_dir
from app.auth import router as auth_router
from app.users import router as users_router
from app.decision import router as decision_router
from app.history import router as history_router
from app.health import router as health_router
from app.middleware import KillSwitchMiddleware, IdempotencyMiddleware, TimeoutMiddleware, RateLimitMiddleware
from app.database import init_db

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
app.include_router(decision_router, prefix="/decision", tags=["Decision"])
app.include_router(history_router, prefix="/history", tags=["History"])
app.include_router(health_router, prefix="/health", tags=["Health"])

@app.on_event("startup")
def on_startup():
    ensure_upload_dir()
    init_db()

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/")
async def root():
    return {"message": "Handled backend running with KillSwitch, OTP, idempotency, and timeout!"}
