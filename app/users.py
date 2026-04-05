from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session
from passlib.hash import pbkdf2_sha256
from app.database import get_db
from app.models import User
from app.schemas import UserOut, UserUpdate, UserProfileOut, UserProfileUpdate, ChangePassword
from app.dependencies import get_current_user
from app.email_utils import send_email, account_deleted_email_html
from app.pagination import paginate

router = APIRouter()

def normalize_email(email: str) -> str:
    return email.strip().lower()

@router.get("/", response_model=list[UserOut])
def get_all_users(pagination: dict = Depends(paginate), db: Session = Depends(get_db)):
    limit, offset = pagination["limit"], pagination["offset"]
    result = db.execute(select(User).limit(limit).offset(offset))
    users = result.scalars().all()
    return users

@router.get("/profile/{user_id}", response_model=UserProfileOut)
def get_profile_by_id(user_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # Require auth, but allow fetching any user's editable fields by id
    result = db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/me", response_model=UserProfileOut)
def update_my_profile(
    payload: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    if payload.email is not None:
        new_email = normalize_email(payload.email)
        existing = db.execute(select(User).where(User.email == new_email, User.id != current_user.id)).scalars().first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        current_user.email = new_email

    if payload.username is not None:
        current_user.username = payload.username
    if payload.allergic is not None:
        current_user.allergic = payload.allergic
    if payload.description is not None:
        current_user.description = payload.description

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user

@router.put("/me/password")
def change_password(
    payload: ChangePassword,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    if not pbkdf2_sha256.verify(payload.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Old password is incorrect")
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    current_user.password_hash = pbkdf2_sha256.hash(payload.new_password)
    db.add(current_user)
    db.commit()
    return {"message": "Password updated successfully"}

@router.delete("/me")
def delete_my_account(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    email_to = current_user.email
    db.delete(current_user)
    db.commit()
    background_tasks.add_task(
        send_email,
        subject="Your Handled account was deleted",
        email_to=email_to,
        body=account_deleted_email_html()
    )
    return {"message": "Account deleted successfully"}

@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    result = db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, user: UserUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # Basic example: allow only self updates here
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not allowed")

    data = user.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(current_user, key, value)

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user
