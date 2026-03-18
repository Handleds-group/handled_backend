
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime

from app.database import get_db, get_redis
from app import schemas
from app.utils import get_current_user, rate_limit

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

@router.get("/health")
async def decision_health():
    """Health check for decision engine"""
    return {"status": "healthy", "service": "decision-engine"}

# Add decision endpoints later