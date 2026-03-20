import os
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import redis
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    raise RuntimeError("REDIS_URL is not set in environment")

def _normalize_redis_url(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    # If ssl flags are present, use rediss:// and drop "ssl" param
    has_ssl_flag = "ssl" in query or "ssl_cert_reqs" in query
    scheme = parsed.scheme
    if has_ssl_flag and scheme == "redis":
        scheme = "rediss"

    if "ssl" in query:
        query.pop("ssl", None)

    cleaned = parsed._replace(scheme=scheme, query=urlencode(query, doseq=True))
    return urlunparse(cleaned)

def get_redis_client() -> redis.Redis:
    normalized = _normalize_redis_url(REDIS_URL)
    return redis.from_url(normalized, decode_responses=True)

redis_client = get_redis_client()
