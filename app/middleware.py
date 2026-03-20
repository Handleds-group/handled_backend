import asyncio
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.health import check_services
from app.idempotency import redis_client

# --------------------------
# Kill Switch / Fail-Fast
# --------------------------
class KillSwitchMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Allow docs/metadata even if dependencies are down
        if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)
        healthy, msg = await check_services()
        if not healthy:
            return JSONResponse({"error": f"Service unavailable: {msg}"}, status_code=503)
        return await call_next(request)

# --------------------------
# Idempotency Middleware
# --------------------------
class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method in ["POST", "PUT"]:
            key = request.headers.get("Idempotency-Key")
            if key:
                exists = redis_client.get(key)
                if exists:
                    return JSONResponse({"detail": "Duplicate request detected"}, status_code=409)
                redis_client.set(key, "1", ex=300)  # Store key for 5 minutes
        return await call_next(request)

# --------------------------
# Timeout Middleware
# --------------------------
class TimeoutMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, timeout: int = 20):
        super().__init__(app)
        self.timeout = timeout

    async def dispatch(self, request, call_next):
        try:
            # Run the request with a timeout
            return await asyncio.wait_for(call_next(request), timeout=self.timeout)
        except asyncio.TimeoutError:
            return JSONResponse(
                {"detail": f"Request timed out after {self.timeout} seconds"},
                status_code=504
            )

# --------------------------
# Rate Limiting Middleware
# --------------------------
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute

    async def dispatch(self, request, call_next):
        # Skip rate limiting for docs
        if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        window = int(time.time() // 60)
        key = f"rate:{client_ip}:{window}"

        try:
            count = redis_client.incr(key)
            if count == 1:
                redis_client.expire(key, 60)
            if count > self.requests_per_minute:
                return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
        except Exception:
            # If Redis is down, do not block requests
            pass

        return await call_next(request)
