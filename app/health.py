from fastapi import APIRouter
from sqlalchemy import text
import anyio
from app.database import auth_engine, supabase_engine
from app.idempotency import redis_client

router = APIRouter()

def _check_db(engine):
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

def _check_redis():
    redis_client.ping()

async def check_services():
    # Check databases
    try:
        await anyio.to_thread.run_sync(_check_db, auth_engine)
    except Exception as exc:
        return False, f"auth database error: {exc}"

    try:
        await anyio.to_thread.run_sync(_check_db, supabase_engine)
    except Exception as exc:
        return False, f"supabase database error: {exc}"

    # Check Redis
    try:
        await anyio.to_thread.run_sync(_check_redis)
    except Exception as exc:
        return False, f"redis error: {exc}"

    return True, "ok"

# Basic health check endpoint
@router.get("/")
async def health_check():
    healthy, msg = await check_services()
    if healthy:
        return {"status": "ok"}
    return {"status": "error", "detail": msg}
