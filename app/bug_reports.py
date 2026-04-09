from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import BugReport, User
from app.schemas import BugReportCreate, BugReportOut

router = APIRouter()

@router.post("/", response_model=BugReportOut, status_code=201)
def create_bug_report(payload: BugReportCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    user_id = data.get("user_id")

    if user_id is not None:
        user = db.execute(select(User.id).where(User.id == user_id)).scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

    report = BugReport(**data)
    db.add(report)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid bug report payload") from exc
    db.refresh(report)
    return report
