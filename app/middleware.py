import asyncio
import base64
import hashlib
import json
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
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
    IDEMPOTENT_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
    KEY_PREFIX = "idempotency"
    LOCK_TTL_SECONDS = 60
    RESPONSE_TTL_SECONDS = 60 * 60 * 24
    REPLAY_HEADERS = {"content-type"}
    EXCLUDED_PATHS = {
        "/payments/webhook",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    async def _read_body(self, request):
        body = await request.body()

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        request._receive = receive
        return body

    def _request_fingerprint(self, request, body: bytes) -> str:
        payload = {
            "method": request.method,
            "path": request.url.path,
            "query": str(request.url.query),
            "body_sha256": hashlib.sha256(body).hexdigest(),
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _cache_key(self, raw_key: str) -> str:
        hashed_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        return f"{self.KEY_PREFIX}:response:{hashed_key}"

    def _lock_key(self, raw_key: str) -> str:
        hashed_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        return f"{self.KEY_PREFIX}:lock:{hashed_key}"

    def _response_from_cache(self, cached_value: str):
        try:
            cached = json.loads(cached_value)
            body = base64.b64decode(cached["body"])
            headers = cached.get("headers") or {}
            response = Response(
                content=body,
                status_code=int(cached["status_code"]),
                media_type=None,
                headers=headers,
            )
            response.headers["Idempotency-Status"] = "replayed"
            return response
        except Exception:
            return None

    async def _response_to_cache_payload(self, response, fingerprint: str):
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        headers = {
            key: value
            for key, value in response.headers.items()
            if key.lower() in self.REPLAY_HEADERS
        }
        payload = {
            "fingerprint": fingerprint,
            "status_code": response.status_code,
            "headers": headers,
            "body": base64.b64encode(body).decode("ascii"),
        }
        replay_response = Response(
            content=body,
            status_code=response.status_code,
            media_type=None,
            headers=dict(response.headers),
        )
        replay_response.headers["Idempotency-Status"] = "created"
        return payload, replay_response

    async def dispatch(self, request, call_next):
        if request.method not in self.IDEMPOTENT_METHODS:
            return await call_next(request)
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        raw_key = request.headers.get("Idempotency-Key")
        if not raw_key:
            return await call_next(request)

        body = await self._read_body(request)
        fingerprint = self._request_fingerprint(request, body)
        cache_key = self._cache_key(raw_key)
        lock_key = self._lock_key(raw_key)

        try:
            cached_value = redis_client.get(cache_key)
            if cached_value:
                cached_response = self._response_from_cache(cached_value)
                if cached_response:
                    cached_payload = json.loads(cached_value)
                    if cached_payload.get("fingerprint") != fingerprint:
                        return JSONResponse(
                            {"detail": "Idempotency-Key was already used for a different request"},
                            status_code=409,
                        )
                    return cached_response

            lock_token = str(uuid.uuid4())
            lock_acquired = redis_client.set(lock_key, lock_token, ex=self.LOCK_TTL_SECONDS, nx=True)
            if not lock_acquired:
                return JSONResponse(
                    {"detail": "Request with this Idempotency-Key is already processing"},
                    status_code=409,
                    headers={"Retry-After": "1"},
                )
        except Exception:
            return await call_next(request)

        try:
            response = await call_next(request)
            if 200 <= response.status_code < 400:
                payload, replay_response = await self._response_to_cache_payload(response, fingerprint)
                try:
                    redis_client.set(cache_key, json.dumps(payload), ex=self.RESPONSE_TTL_SECONDS)
                except Exception:
                    pass
                return replay_response
            return response
        finally:
            try:
                if redis_client.get(lock_key) == lock_token:
                    redis_client.delete(lock_key)
            except Exception:
                pass

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
    def build_cache_key(
        cls,
        user_input: str,
        model: str,
        profile_context: str = "",
        reply_context: str = "",
    ) -> str:
        normalized_payload = {
            "user_input": (user_input or "").strip(),
            "model": model,
            "profile_context": (profile_context or "").strip(),
            "reply_context": (reply_context or "").strip(),
        }
        serialized = json.dumps(normalized_payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return f"{cls.KEY_PREFIX}:{digest}"

    @classmethod
    def get_cached_response(
        cls,
        user_input: str,
        model: str,
        profile_context: str = "",
        reply_context: str = "",
    ):
        cache_key = cls.build_cache_key(
            user_input=user_input,
            model=model,
            profile_context=profile_context,
            reply_context=reply_context,
        )
        cached_value = redis_client.get(cache_key)
        if not cached_value:
            return None

        try:
            return json.loads(cached_value)
        except json.JSONDecodeError:
            redis_client.delete(cache_key)
            return None

    @classmethod
    def set_cached_response(
        cls,
        user_input: str,
        model: str,
        response_text: str,
        profile_context: str = "",
        reply_context: str = "",
    ):
        cache_key = cls.build_cache_key(
            user_input=user_input,
            model=model,
            profile_context=profile_context,
            reply_context=reply_context,
        )
        payload = {
            "response": response_text
        }
        redis_client.set(cache_key, json.dumps(payload), ex=cls.TTL_SECONDS)
