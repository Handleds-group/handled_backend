from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Notification

router = APIRouter()

@router.get("/me")
def my_notifications(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    notes = db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
    ).scalars().all()
    return {"count": len(notes), "data": notes}

@router.post("/me/{notification_id}/read")
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    note = db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    ).scalars().first()
    if not note:
        return {"message": "Not found"}
    note.is_read = True
    db.add(note)
    db.commit()
    return {"message": "Marked as read"}
