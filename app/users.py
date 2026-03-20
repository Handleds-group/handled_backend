from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.schemas import UserOut, UserUpdate
from app.dependencies import get_current_user
from app.pagination import paginate

router = APIRouter()

@router.get("/", response_model=list[UserOut])
def get_all_users(pagination: dict = Depends(paginate), db: Session = Depends(get_db)):
    limit, offset = pagination["limit"], pagination["offset"]
    result = db.execute(select(User).limit(limit).offset(offset))
    users = result.scalars().all()
    return users

@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int):
    # Placeholder for fetching single user
    raise HTTPException(status_code=501, detail="Not implemented")

@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, user: UserUpdate, current_user=Depends(get_current_user)):
    # Placeholder for updating profile
    raise HTTPException(status_code=501, detail="Not implemented")
