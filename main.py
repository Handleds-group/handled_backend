from fastapi import FastAPI
from app.auth import router as auth_router
from app.users import router as users_router
from app.decision import router as decision_router
from app.history import router as history_router
from app.health import router as health_router
from app.middleware import KillSwitchMiddleware, IdempotencyMiddleware, TimeoutMiddleware
from app.database import init_db

app = FastAPI(title="Handled Backend")

# --------------------------
# Middleware
# --------------------------
app.add_middleware(TimeoutMiddleware, timeout=20)     # Custom timeout
app.add_middleware(KillSwitchMiddleware)             # Kill switch for DB/Redis/Paystack
app.add_middleware(IdempotencyMiddleware)            # Idempotency for POST/PUT

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
    init_db()

@app.get("/")
async def root():
    return {"message": "Handled backend running with KillSwitch, OTP, idempotency, and timeout!"}
