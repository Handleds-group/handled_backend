"""
Admin Security Module
- Rate limiting for admin endpoints
- IP blocking for admin panel
- Failed login attempt tracking
"""

import time
from typing import Optional, Set
from app.idempotency import redis_client

# Configuration
ADMIN_RATE_LIMIT = 30  # Admin requests per minute
ADMIN_LOGIN_ATTEMPTS_LIMIT = 5  # Failed attempts before block
ADMIN_LOGIN_BLOCK_DURATION = 900  # 15 minutes in seconds
ADMIN_IP_BLOCK_DURATION = 3600  # 1 hour

# IP blocklist keys
BLOCKED_IPS_KEY = "admin:blocked_ips"
LOGIN_ATTEMPTS_KEY = "admin:login_attempts"
ADMIN_RATE_LIMIT_KEY = "admin:rate_limit"


class AdminSecurityManager:
    """Manages admin security: rate limiting, IP blocking, login attempts"""

    @staticmethod
    def is_ip_blocked(client_ip: str) -> bool:
        """Check if an IP is blocked from admin access"""
        if not client_ip:
            return False
        try:
            blocked = redis_client.sismember(BLOCKED_IPS_KEY, client_ip)
            return bool(blocked)
        except Exception:
            return False

    @staticmethod
    def block_ip(client_ip: str, duration: int = ADMIN_IP_BLOCK_DURATION) -> None:
        """Block an IP address from admin access"""
        if not client_ip:
            return
        try:
            redis_client.sadd(BLOCKED_IPS_KEY, client_ip)
            redis_client.expire(BLOCKED_IPS_KEY, duration)
        except Exception:
            pass

    @staticmethod
    def unblock_ip(client_ip: str) -> None:
        """Unblock an IP address"""
        if not client_ip:
            return
        try:
            redis_client.srem(BLOCKED_IPS_KEY, client_ip)
        except Exception:
            pass

    @staticmethod
    def get_blocked_ips() -> Set[str]:
        """Get all currently blocked IPs"""
        try:
            return set(redis_client.smembers(BLOCKED_IPS_KEY) or [])
        except Exception:
            return set()

    @staticmethod
    def record_failed_login(client_ip: str) -> int:
        """Record a failed login attempt and return current attempt count"""
        if not client_ip:
            return 0
        try:
            key = f"{LOGIN_ATTEMPTS_KEY}:{client_ip}"
            count = redis_client.incr(key)
            if count == 1:
                redis_client.expire(key, ADMIN_LOGIN_BLOCK_DURATION)
            return count
        except Exception:
            return 0

    @staticmethod
    def reset_login_attempts(client_ip: str) -> None:
        """Reset failed login attempts for an IP"""
        if not client_ip:
            return
        try:
            key = f"{LOGIN_ATTEMPTS_KEY}:{client_ip}"
            redis_client.delete(key)
        except Exception:
            pass

    @staticmethod
    def get_login_attempts(client_ip: str) -> int:
        """Get failed login attempt count for an IP"""
        if not client_ip:
            return 0
        try:
            key = f"{LOGIN_ATTEMPTS_KEY}:{client_ip}"
            return int(redis_client.get(key) or 0)
        except Exception:
            return 0

    @staticmethod
    def check_admin_rate_limit(client_ip: str, limit: int = ADMIN_RATE_LIMIT) -> tuple[bool, int]:
        """
        Check if admin IP exceeded rate limit
        Returns: (is_allowed, remaining_requests)
        """
        if not client_ip:
            return True, limit

        try:
            window = int(time.time() // 60)
            key = f"{ADMIN_RATE_LIMIT_KEY}:{client_ip}:{window}"
            count = redis_client.incr(key)
            if count == 1:
                redis_client.expire(key, 60)

            remaining = max(0, limit - count)
            is_allowed = count <= limit
            return is_allowed, remaining
        except Exception:
            # If Redis fails, allow the request
            return True, limit

    @staticmethod
    def get_admin_stats() -> dict:
        """Get current admin security statistics"""
        try:
            blocked_count = redis_client.scard(BLOCKED_IPS_KEY) or 0
            blocked_ips = AdminSecurityManager.get_blocked_ips()
            return {
                "blocked_ips_count": blocked_count,
                "blocked_ips": list(blocked_ips),
            }
        except Exception:
            return {
                "blocked_ips_count": 0,
                "blocked_ips": [],
            }
