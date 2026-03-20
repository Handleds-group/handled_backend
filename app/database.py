import os
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in environment")

connect_args = {}
parsed = urlparse(DATABASE_URL)
query = parse_qs(parsed.query)
sslmode = (query.get("sslmode", [None])[0] or "").lower()
if sslmode == "require":
    # asyncpg expects ssl=True/SSLContext; "require" is accepted as a truthy ssl config
    connect_args["ssl"] = "require"

# Remove sslmode from URL to avoid asyncpg complaining about it
if "sslmode" in query:
    query.pop("sslmode", None)
    cleaned = parsed._replace(query=urlencode(query, doseq=True))
    database_url = urlunparse(cleaned)
else:
    database_url = DATABASE_URL

engine = create_async_engine(
    database_url,
    echo=True,
    future=True,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args=connect_args,
)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# Dependency
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    # Import here to avoid circular imports at module load time.
    from app.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
