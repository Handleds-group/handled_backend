import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in environment")

# Force a normal psycopg2 (sync) connection even if env uses asyncpg
if "postgresql+asyncpg://" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)

engine = create_engine(
    DATABASE_URL,
    echo=True,
    future=True,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 20},
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    # Import here to avoid circular imports at module load time.
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    _ensure_user_columns()


def _ensure_user_columns():
    # Lightweight auto-migration for missing columns in "users" table.
    # This avoids runtime failures when the DB schema lags behind models.
    alter_statements = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_premium BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS plan VARCHAR",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_id VARCHAR",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS tokens_used INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE bug_reports ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
    ]
    with engine.begin() as conn:
        for stmt in alter_statements:
            conn.execute(text(stmt))
