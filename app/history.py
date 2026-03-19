from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime

from database import get_db, get_redis
import schemas
from utils import get_current_user, rate_limit

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

@router.get("/health")
async def history_health():
    """Health check for history service"""
    return {"status": "healthy", "service": "history"}

# Add history endpoints later