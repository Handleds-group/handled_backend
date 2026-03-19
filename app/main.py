from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import logging
import time
from typing import Dict
import sys


from database import engine, check_db_health, check_redis_health
import auth, users, decisions, history
from utils import kill_switch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Kill switch state
is_running = True

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting Handled API...")
    
    # Pre-flight checks
    if not await check_db_health():
        logger.error("❌ Database connection failed")
        sys.exit("❌ Database connection failed")
    
    if not await check_redis_health():
        logger.error("❌ Redis connection failed")
        sys.exit("❌ Redis connection failed")
    
    logger.info("✅ All systems ready")
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Handled API...")
    await engine.dispose()

# Initialize FastAPI
app = FastAPI(
    title="Handled API",
    description="Decision-making support for ADHD users",
    version="1.0.0",
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Middleware for request timing and kill switch
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    global is_running
    
    # Check kill switch
    if not is_running:
        return Response(
            content='{"detail": "Server is in maintenance mode"}',
            status_code=503,
            media_type="application/json"
        )
    
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    
    # Log slow requests (>1s)
    if process_time > 1:
        logger.warning(f"Slow request: {request.method} {request.url.path} took {process_time:.2f}s")
    
    return response

# Health check endpoints
@app.get("/health/live")
async def health_live():
    """Basic liveness check"""
    return {"status": "alive", "timestamp": time.time()}

@app.get("/health/ready")
async def health_ready():
    """Readiness check - verifies all dependencies"""
    db_health = await check_db_health()
    redis_health = await check_redis_health()
    
    if not db_health or not redis_health:
        return Response(
            status_code=503,
            content={"status": "not ready", "db": db_health, "redis": redis_health}
        )
    
    return {"status": "ready", "db": db_health, "redis": redis_health}

@app.get("/health/db")
async def health_db():
    """Database health check"""
    return {"status": "healthy" if await check_db_health() else "unhealthy"}

# Kill switch endpoint (protected, should be admin only)
@app.post("/admin/kill-switch")
async def toggle_kill_switch(state: bool):
    global is_running
    is_running = state
    logger.warning(f"🔴 Kill switch toggled to: {state}")
    return {"kill_switch": is_running}

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(decisions.router, prefix="/api/decisions", tags=["Decisions"])
app.include_router(history.router, prefix="/api/history", tags=["History"])

@app.get("/")
async def root():
    return {
        "message": "Welcome to Handled API",
        "version": "1.0.0",
        "docs": "/docs"
    }