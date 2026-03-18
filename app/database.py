from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
import redis.asyncio as redis
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

# PostgreSQL connection with connection pooling
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/handled")

engine = create_async_engine(
    DATABASE_URL,
    echo=True if os.getenv("DEBUG") == "True" else False,
    pool_size=20,  # Connection pool size
    max_overflow=10,  # Extra connections beyond pool_size
    pool_timeout=30,  # Timeout for getting connection from pool
    pool_recycle=1800,  # Recycle connections after 30 minutes
    pool_pre_ping=True,  # Verify connections before using
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()

# Redis connection for caching, rate limiting, idempotency
redis_client: Optional[redis.Redis] = None

async def init_redis():
    global redis_client
    redis_client = await redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379"),
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,  # Connection pool
        socket_timeout=5,  # Socket timeout
        socket_connect_timeout=5,
        retry_on_timeout=True,
        health_check_interval=30,  # Check connection health
    )
    return redis_client

async def get_redis():
    if redis_client is None:
        await init_redis()
    return redis_client

async def get_db():
    """Dependency for getting database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Health checks
async def check_db_health() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception as e:
        print(f"Database health check failed: {e}")
        return False

async def check_redis_health() -> bool:
    try:
        redis = await get_redis()
        await redis.ping()
        return True
    except Exception as e:
        print(f"Redis health check failed: {e}")
        return False