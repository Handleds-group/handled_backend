from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User
from app.schemas import UserOut, UserUpdate
from app.dependencies import get_current_user
from app.pagination import paginate

router = APIRouter()

@router.get("/", response_model=list[UserOut])
async def get_all_users(pagination: dict = Depends(paginate), db: AsyncSession = Depends(get_db)):
    limit, offset = pagination["limit"], pagination["offset"]
    result = await db.execute(select(User).limit(limit).offset(offset))
    users = result.scalars().all()
    return users

@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: int):
    # Placeholder for fetching single user
    raise HTTPException(status_code=501, detail="Not implemented")

@router.put("/{user_id}", response_model=UserOut)
async def update_user(user_id: int, user: UserUpdate, current_user=Depends(get_current_user)):
    # Placeholder for updating profile
    raise HTTPException(status_code=501, detail="Not implemented")
