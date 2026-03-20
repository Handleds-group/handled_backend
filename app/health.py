from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
import redis.asyncio as redis
import os
import httpx

router = APIRouter()

REDIS_URL = os.getenv("REDIS_URL")
PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET_KEY")

async def check_services():
    # DB check
    try:
        async for db in get_db():
            await db.execute("SELECT 1")
    except Exception as e:
        return False, f"DB error: {e}"

    # Redis check
    try:
        redis_client = redis.from_url(REDIS_URL)
        await redis_client.ping()
        await redis_client.close()
    except Exception as e:
        return False, f"Redis error: {e}"

    # Paystack API check (placeholder)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.paystack.co/transaction/verify/0",
                headers={"Authorization": f"Bearer {PAYSTACK_SECRET}"}
            )
            if resp.status_code not in [200, 404]:  # 404 expected for id=0
                return False, "Paystack API issue"
    except Exception as e:
        return False, f"Paystack error: {e}"

    return True, "All services healthy"

@router.get("/")
async def health_check():
    healthy, msg = await check_services()
    return {"healthy": healthy, "message": msg}
