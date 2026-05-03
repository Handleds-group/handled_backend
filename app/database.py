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
    pool_reset_on_return=None,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,  # Recycle connections after 1 hour to prevent idle timeout
    pool_timeout=30,
    connect_args={
        "connect_timeout": 20,
        "options": "-c statement_timeout=300000",  # 5 minute statement timeout
    },
)
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        try:
            if db.in_transaction():
                try:
                    db.rollback()
                except Exception as rollback_error:
                    rollback_message = str(rollback_error).lower()
                    if any(
                        marker in rollback_message
                        for marker in ("idle transaction timeout", "connection closed", "ssl syscall error", "eof detected")
                    ):
                        db.invalidate()
                    else:
                        raise
            db.close()
        except Exception as e:
            # Cleanup errors during request teardown should not turn a completed response
            # into a server error, especially when a background task delays session close.
            message = str(e).lower()
            if any(
                marker in message
                for marker in ("idle transaction timeout", "connection closed", "ssl syscall error", "eof detected")
            ):
                db.invalidate()
                print(f"[DB Cleanup Warning] {e}")
                return
            raise

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
