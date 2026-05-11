import asyncio
import hashlib
import json
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


# Admin Rate Limiting Middleware
class AdminRateLimitMiddleware(BaseHTTPMiddleware):
    """Stricter rate limiting for admin endpoints (30 req/min vs 60 req/min)"""
    def __init__(self, app, requests_per_minute: int = 30):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute

    async def dispatch(self, request, call_next):
        # Only apply to admin endpoints
        if not request.url.path.startswith("/admin"):
            return await call_next(request)

        # Skip docs
        if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        from app.admin_security import AdminSecurityManager

        client_ip = request.client.host if request.client else "unknown"

        # Check if IP is blocked
        if AdminSecurityManager.is_ip_blocked(client_ip):
            return JSONResponse(
                {"detail": "Your IP address has been blocked due to suspicious activity. Please try again later."},
                status_code=403
            )

        # Check rate limit
        is_allowed, remaining = AdminSecurityManager.check_admin_rate_limit(client_ip, self.requests_per_minute)
        if not is_allowed:
            return JSONResponse(
                {"detail": "Admin rate limit exceeded. Maximum 30 requests per minute."},
                status_code=429
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


class DecisionCacheMiddleware:
    TTL_SECONDS = 60 * 60 * 24
    KEY_PREFIX = "decision_cache"

    @classmethod
    def build_cache_key(cls, user_input: str, model: str) -> str:
        normalized_payload = {
            "user_input": (user_input or "").strip(),
            "model": model
        }
        serialized = json.dumps(normalized_payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return f"{cls.KEY_PREFIX}:{digest}"

    @classmethod
    def get_cached_response(cls, user_input: str, model: str):
        cache_key = cls.build_cache_key(user_input=user_input, model=model)
        cached_value = redis_client.get(cache_key)
        if not cached_value:
            return None

        try:
            return json.loads(cached_value)
        except json.JSONDecodeError:
            redis_client.delete(cache_key)
            return None

    @classmethod
    def set_cached_response(cls, user_input: str, model: str, response_text: str):
        cache_key = cls.build_cache_key(user_input=user_input, model=model)
        payload = {
            "response": response_text
        }
        redis_client.set(cache_key, json.dumps(payload), ex=cls.TTL_SECONDS)
