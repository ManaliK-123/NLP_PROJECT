from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Decision, DecisionHistory
from app.schemas.schemas import DecisionRead

router = APIRouter(prefix="/api/decisions", tags=["decisions"])

@router.get("", response_model=List[DecisionRead])
def list_decisions(
    meeting_id: Optional[int] = None,
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Decision)
    if meeting_id:
        query = query.filter(Decision.meeting_id == meeting_id)
    if project_id:
        query = query.filter(Decision.project_id == project_id)
    if status:
        query = query.filter(Decision.status == status)
    return query.order_by(Decision.created_at.desc()).all()

@router.patch("/{id}/status")
def update_decision_status(id: int, new_status: str, note: Optional[str] = None, db: Session = Depends(get_db)):
    decision = db.query(Decision).filter(Decision.id == id).first()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    old_status = decision.status
    decision.status = new_status
    db.add(DecisionHistory(
        decision_id=decision.id,
        change_type="Status Change",
        details=note or f"Status changed from {old_status} to {new_status}"
    ))
    db.commit()
    db.refresh(decision)
    return {"success": True, "decision": decision}
