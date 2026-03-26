from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import BugReport
from app.schemas import BugReportCreate, BugReportOut

router = APIRouter()

@router.post("/", response_model=BugReportOut, status_code=201)
def create_bug_report(payload: BugReportCreate, db: Session = Depends(get_db)):
    report = BugReport(**payload.model_dump())
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
