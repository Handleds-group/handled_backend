import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

NEON_DB = os.getenv("NEON_DB")
SUPABASE_DB = os.getenv("SUPABASE_DB")

if not NEON_DB:
    raise RuntimeError("NEON_DB is not set in environment")
if not SUPABASE_DB:
    raise RuntimeError("SUPABASE_DB is not set in environment")


def _sync_url(url: str) -> str:
    # Force a normal psycopg2 (sync) connection even if env uses asyncpg.
    if "postgresql+asyncpg://" in url:
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    return url


def _create_db_engine(url: str):
    return create_engine(
        _sync_url(url),
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


auth_engine = _create_db_engine(NEON_DB)
supabase_engine = _create_db_engine(SUPABASE_DB)

AuthSessionLocal = sessionmaker(
    bind=auth_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)
SupabaseSessionLocal = sessionmaker(
    bind=supabase_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

def _cleanup_db(db):
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


def get_auth_db():
    db = AuthSessionLocal()
    try:
        yield db
    finally:
        _cleanup_db(db)


def get_supabase_db():
    db = SupabaseSessionLocal()
    try:
        yield db
    finally:
        _cleanup_db(db)

def init_db():
    # Import here to avoid circular imports at module load time.
    from app.models import BugReport, DecisionHistory, Notification, OTP, PaymentTransaction, User, Wallet, WithdrawalRequest

    auth_tables = [
        User.__table__,
        OTP.__table__,
        PaymentTransaction.__table__,
        Wallet.__table__,
        WithdrawalRequest.__table__,
    ]
    supabase_tables = [
        DecisionHistory.__table__,
        BugReport.__table__,
        Notification.__table__,
    ]
    User.metadata.create_all(bind=auth_engine, tables=auth_tables)
    User.metadata.create_all(bind=supabase_engine, tables=supabase_tables)
    _ensure_auth_columns()
    _ensure_supabase_columns()


def _ensure_auth_columns():
    # Lightweight auto-migration for missing columns in "users" table.
    # This avoids runtime failures when the DB schema lags behind models.
    alter_statements = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_premium BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS plan VARCHAR",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_id VARCHAR",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS tokens_used INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP WITH TIME ZONE",
    ]
    with auth_engine.begin() as conn:
        for stmt in alter_statements:
            conn.execute(text(stmt))


def _ensure_supabase_columns():
    alter_statements = [
        "ALTER TABLE bug_reports ADD COLUMN IF NOT EXISTS user_id INTEGER",
        "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS user_id INTEGER",
        "ALTER TABLE bug_reports DROP CONSTRAINT IF EXISTS bug_reports_user_id_fkey",
        "ALTER TABLE notifications DROP CONSTRAINT IF EXISTS notifications_user_id_fkey",
    ]
    with supabase_engine.begin() as conn:
        for stmt in alter_statements:
            conn.execute(text(stmt))
