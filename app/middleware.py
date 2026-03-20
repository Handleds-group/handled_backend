import asyncio
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.health import check_services
from app.idempotency import redis

# --------------------------
# Kill Switch / Fail-Fast
# --------------------------
class KillSwitchMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
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
                exists = await redis.get(key)
                if exists:
                    return JSONResponse({"detail": "Duplicate request detected"}, status_code=409)
                await redis.set(key, "1", ex=300)  # Store key for 5 minutes
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