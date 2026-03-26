# decision_routes.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from .decision_service import generate_decision
from .database import get_db   # your existing DB connection

from .models import DecisionHistory  # we’ll define below

router = APIRouter(prefix="/decisions", tags=["Decisions"])


# 🧠 CREATE DECISION
@router.post("/make")
async def make_decision(user_input: str, user_id: str, db: Session = Depends(get_db)):
    
    if not user_input:
        raise HTTPException(status_code=400, detail="Input is required")

    ai_response = await generate_decision(user_input)

    decision = DecisionHistory(
        id=str(uuid.uuid4()),
        user_id=user_id,
        input_text=user_input,
        ai_response=ai_response,
        created_at=datetime.utcnow()
    )

    db.add(decision)
    db.commit()

    return {
        "message": "Decision generated successfully",
        "data": {
            "decision_id": decision.id,
            "response": ai_response
        }
    }


# 📜 GET USER HISTORY
@router.get("/history/{user_id}")
async def get_history(user_id: str, db: Session = Depends(get_db)):

    history = db.query(DecisionHistory)\
        .filter(DecisionHistory.user_id == user_id)\
        .order_by(DecisionHistory.created_at.desc())\
        .all()

    return {
        "count": len(history),
        "data": history
    }


# 🗑️ DELETE ONE DECISION
@router.delete("/{decision_id}")
async def delete_decision(decision_id: str, db: Session = Depends(get_db)):

    decision = db.query(DecisionHistory)\
        .filter(DecisionHistory.id == decision_id)\
        .first()

    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    db.delete(decision)
    db.commit()

    return {"message": "Deleted successfully"}