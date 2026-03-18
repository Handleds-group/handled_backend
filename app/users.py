from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
import os
import shutil
from datetime import datetime

from app.database import get_db, get_redis
from app import schemas, models
from app.utils import get_current_user, rate_limit, check_idempotency, upload_to_cdn

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

@router.get("/me", response_model=schemas.UserProfile)
@rate_limit(max_requests=30, window_seconds=60)
async def get_my_profile(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    """Get current user's profile"""
    
    # Check cache first
    cache_key = f"user:profile:{token}"
    cached = await redis.get(cache_key)
    if cached:
        return schemas.UserProfile.parse_raw(cached)
    
    user = await get_current_user(token, db)
    
    # Cache for 5 minutes
    profile = schemas.UserProfile.from_orm(user)
    await redis.setex(cache_key, 300, profile.json())
    
    return profile

@router.get("/{user_id}", response_model=schemas.UserProfile)
@rate_limit(max_requests=30, window_seconds=60)
async def get_user_profile(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    """Get any user's profile by ID"""
    
    # Check cache
    cache_key = f"user:profile:{user_id}"
    cached = await redis.get(cache_key)
    if cached:
        return schemas.UserProfile.parse_raw(cached)
    
    result = await db.execute(
        select(models.User).where(models.User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Cache for 5 minutes
    profile = schemas.UserProfile.from_orm(user)
    await redis.setex(cache_key, 300, profile.json())
    
    return profile

@router.patch("/me", response_model=schemas.UserProfile)
@rate_limit(max_requests=10, window_seconds=3600)
@check_idempotency(timeout=300)
async def update_profile(
    request: Request,
    updates: schemas.UserProfileUpdate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    """Update current user's profile"""
    
    user = await get_current_user(token, db)
    
    # Check username availability if changing
    if updates.username and updates.username != user.username:
        result = await db.execute(
            select(models.User).where(models.User.username == updates.username)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
    
    # Update fields
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(user)
    
    # Invalidate caches
    await redis.delete(f"user:profile:{token}")
    await redis.delete(f"user:profile:{user.id}")
    
    return schemas.UserProfile.from_orm(user)

@router.post("/me/profile-pic")
@rate_limit(max_requests=5, window_seconds=3600)
async def upload_profile_pic(
    request: Request,
    file: UploadFile = File(...),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    """Upload profile picture"""
    
    user = await get_current_user(token, db)
    
    # Validate file
    if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG, and WebP images are allowed"
        )
    
    # Check file size (max 5MB)
    file.file.seek(0, 2)  # Seek to end
    size = file.file.tell()
    file.file.seek(0)  # Reset
    
    if size > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large (max 5MB)"
        )
    
    # Upload to CDN/storage (placeholder)
    file_url = await upload_to_cdn(file, folder="profile-pics")
    
    # Update user
    user.profile_pic = file_url
    user.updated_at = datetime.utcnow()
    await db.commit()
    
    # Invalidate caches
    await redis.delete(f"user:profile:{token}")
    await redis.delete(f"user:profile:{user.id}")
    
    return {"profile_pic": file_url}

@router.get("/me/login-history", response_model=List[schemas.LoginHistoryResponse])
@rate_limit(max_requests=10, window_seconds=60)
async def get_login_history(
    request: Request,
    skip: int = 0,
    limit: int = 20,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Get user's login history with pagination"""
    
    user = await get_current_user(token, db)
    
    result = await db.execute(
        select(models.LoginHistory)
        .where(models.LoginHistory.user_id == user.id)
        .order_by(models.LoginHistory.login_at.desc())
        .offset(skip)
        .limit(limit)
    )
    history = result.scalars().all()
    
    return history