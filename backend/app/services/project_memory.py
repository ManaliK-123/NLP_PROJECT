from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models.models import Project, Meeting, Task, Decision, Conflict, TaskHistory, DecisionHistory

def get_project_memory_intelligence(db: Session, project_id: int) -> Dict[str, Any]:
    """
    Aggregate cross-meeting intelligence, task lifecycle timelines, and decision drift for a project.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return {"error": "Project not found"}

    meetings = db.query(Meeting).filter(Meeting.project_id == project_id).order_by(Meeting.meeting_date.asc()).all()
    tasks = db.query(Task).filter(Task.project_id == project_id).all()
    decisions = db.query(Decision).filter(Decision.project_id == project_id).all()
    
    # 1. Decision Drift analysis
    drifts = []
    for d in decisions:
        if d.supersedes_previous_decision and d.previous_decision_id:
            prev_d = db.query(Decision).filter(Decision.id == d.previous_decision_id).first()
            if prev_d:
                drifts.append({
                    "topic": d.topic or "Topic Drift",
                    "previous_decision": prev_d.decision,
                    "previous_meeting_id": prev_d.meeting_id,
                    "new_decision": d.decision,
                    "new_meeting_id": d.meeting_id,
                    "reason": d.drift_reason or "Superseded in subsequent discussion",
                    "timestamp": d.created_at
                })

    # 2. Task lifecycle & audit timeline
    task_timeline = []
    for t in tasks:
        history_records = db.query(TaskHistory).filter(TaskHistory.task_id == t.id).order_by(TaskHistory.created_at.asc()).all()
        history_items = [{
            "field": h.field_changed,
            "old": h.old_value,
            "new": h.new_value,
            "note": h.note,
            "timestamp": h.created_at
        } for h in history_records]
        
        task_timeline.append({
            "task_id": t.id,
            "title": t.title,
            "owner": t.owner,
            "current_status": t.status,
            "deadline": t.deadline_text,
            "created_at": t.created_at,
            "history": history_items
        })

    # 3. Responsibility distribution (tasks per owner)
    owner_distribution = {}
    for t in tasks:
        owner = t.owner or "Unassigned"
        owner_distribution[owner] = owner_distribution.get(owner, 0) + 1
        
    owner_chart_data = [{"owner": k, "tasks": v} for k, v in owner_distribution.items()]

    # 4. Unresolved items across all meetings in project
    unresolved_items = []
    for d in decisions:
        if d.status in ("Undecided", "Tentative"):
            unresolved_items.append({
                "type": "decision",
                "title": d.topic or "Undecided Matter",
                "detail": d.decision,
                "meeting_id": d.meeting_id,
                "evidence_timestamp": d.evidence_timestamp
            })
    for t in tasks:
        if t.status in ("Needs Clarification", "Blocked"):
            unresolved_items.append({
                "type": "task",
                "title": t.title,
                "detail": f"Status: {t.status} | Owner: {t.owner}",
                "meeting_id": t.meeting_id,
                "evidence_timestamp": t.evidence_timestamp
            })

    return {
        "project_id": project.id,
        "project_name": project.name,
        "total_meetings": len(meetings),
        "total_tasks": len(tasks),
        "meetings_list": [{"id": m.id, "title": m.title, "date": m.meeting_date} for m in meetings],
        "decision_drifts": drifts,
        "task_timeline": task_timeline,
        "responsibility_distribution": owner_chart_data,
        "unresolved_items": unresolved_items
    }
