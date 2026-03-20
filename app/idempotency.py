# app/middleware/idempotency.py
from fastapi import Request, HTTPException
import redis.asyncio as redis
import os
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)  # modern async redis

async def check_idempotency(request: Request):
    """
    Checks if a request with the same Idempotency-Key has been processed.
    Clients should send 'Idempotency-Key' header.
    """
    key = request.headers.get("Idempotency-Key")
    if not key:
        raise HTTPException(status_code=400, detail="Idempotency-Key missing")

    exists = await redis_client.get(key)
    if exists:
        raise HTTPException(status_code=409, detail="Duplicate request detected")

    # Store the key for 5 minutes to prevent duplicates
    await redis_client.set(key, "1", ex=300)