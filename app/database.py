# app/database.py
import os
from typing import Optional
from dotenv import load_dotenv
import logging

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
import redis.asyncio as redis

load_dotenv()
logger = logging.getLogger(__name__)

# ----------------------------
# PostgreSQL Configuration
# ----------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL is not set")

# 🔥 AUTO-FIX sslmode → ssl for asyncpg
if "sslmode=" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("sslmode=", "ssl=")

# 🔥 ENSURE asyncpg is used
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://",
        "postgresql+asyncpg://"
    )

engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("DEBUG") == "True",
    pool_size=5,
    max_overflow=5,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
    connect_args={"ssl": "require"},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()

# ----------------------------
# Redis Configuration
# ----------------------------
redis_client: Optional[redis.Redis] = None

def _normalize_redis_url(url: str) -> str:
    if "://" not in url:
        return f"redis://{url}"
    return url

async def init_redis() -> redis.Redis:
    global redis_client

    if redis_client is None:
        redis_client = await redis.from_url(
            _normalize_redis_url(os.getenv("REDIS_URL")),
            encoding="utf-8",
            decode_responses=True,
            max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", 20)),
            socket_timeout=float(os.getenv("REDIS_SOCKET_TIMEOUT", 5)),
            socket_connect_timeout=float(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", 5)),
            retry_on_timeout=True,
            health_check_interval=30,
        )
        logger.info("✅ Redis initialized")

    return redis_client

async def get_redis():
    return await init_redis()

# ----------------------------
# DB Dependency
# ----------------------------
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# ----------------------------
# Health checks (FIXED)
# ----------------------------
async def check_db_health() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("✅ Database healthy")
        return True
    except Exception as e:
        logger.error(f"❌ Database error: {e}")
        return False

async def check_redis_health() -> bool:
    try:
        r = await get_redis()
        await r.ping()
        logger.info("✅ Redis healthy")
        return True
    except Exception as e:
        logger.error(f"❌ Redis error: {e}")
        return False