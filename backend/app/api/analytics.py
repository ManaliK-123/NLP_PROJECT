from typing import Dict, Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Meeting, Task, Decision, Conflict, Dependency
from app.services.execution_radar import calculate_execution_radar
from app.llm.provider import llm_provider

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("/dashboard")
def get_dashboard_analytics(db: Session = Depends(get_db)):
    meetings = db.query(Meeting).order_by(Meeting.meeting_date.desc()).all()
    tasks = db.query(Task).all()
    decisions = db.query(Decision).all()
    conflicts = db.query(Conflict).all()
    dependencies = db.query(Dependency).all()

    total_meetings = len(meetings)
    completed_meetings = sum(1 for m in meetings if m.status == "completed")
    
    # Calculate global execution radar
    tasks_dict_list = [t.__dict__ for t in tasks]
    dec_dict_list = [d.__dict__ for d in decisions]
    conf_dict_list = [c.__dict__ for c in conflicts]
    dep_dict_list = [dep.__dict__ for dep in dependencies]

    radar = calculate_execution_radar(tasks_dict_list, dec_dict_list, conf_dict_list, dep_dict_list)

    avg_actionability = (
        round(sum(m.actionability_score for m in meetings) / total_meetings, 1)
        if total_meetings > 0 else 0.0
    )

    # Recent meetings snippet
    recent_meetings = []
    for m in meetings[:5]:
        recent_meetings.append({
            "id": m.id,
            "title": m.title,
            "date": m.meeting_date,
            "status": m.status,
            "actionability_score": m.actionability_score,
            "task_count": len(m.tasks),
            "conflict_count": len(m.conflicts)
        })

    # Upcoming deadlines (sorted)
    upcoming_tasks = []
    for t in tasks:
        if t.status not in ("Completed", "Cancelled") and t.deadline_text:
            upcoming_tasks.append({
                "id": t.id,
                "title": t.title,
                "owner": t.owner,
                "deadline": t.deadline_text,
                "deadline_status": t.deadline_status,
                "priority": t.priority,
                "status": t.status,
                "meeting_id": t.meeting_id
            })

    return {
        "total_meetings": total_meetings,
        "completed_meetings": completed_meetings,
        "avg_actionability": avg_actionability,
        "radar": radar,
        "recent_meetings": recent_meetings,
        "upcoming_tasks": upcoming_tasks[:8],
        "active_ai_provider": llm_provider.get_active_provider_info()
    }
