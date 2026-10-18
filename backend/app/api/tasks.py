from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Task, TaskHistory, Meeting
from app.schemas.schemas import TaskRead, TaskCreate, TaskUpdate

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

@router.get("", response_model=List[TaskRead])
def list_tasks(
    owner: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    meeting_id: Optional[int] = None,
    project_id: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Task)
    if meeting_id:
        query = query.filter(Task.meeting_id == meeting_id)
    if project_id:
        query = query.filter(Task.project_id == project_id)
    if owner:
        query = query.filter(Task.owner.ilike(f"%{owner}%"))
    if status:
        query = query.filter(Task.status == status)
    if priority:
        query = query.filter(Task.priority == priority)
    if search:
        query = query.filter((Task.title.ilike(f"%{search}%")) | (Task.description.ilike(f"%{search}%")))

    return query.order_by(Task.updated_at.desc()).all()

@router.post("", response_model=TaskRead)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    task = Task(**payload.dict())
    db.add(task)
    db.commit()
    db.refresh(task)

    # Add initial history record
    db.add(TaskHistory(task_id=task.id, field_changed="created", old_value=None, new_value=task.status, note="Task created"))
    db.commit()
    return task

@router.patch("/{id}", response_model=TaskRead)
def update_task(id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    update_dict = payload.dict(exclude_unset=True)
    note = update_dict.pop("note", None)

    for field, new_val in update_dict.items():
        old_val = getattr(task, field, None)
        if str(old_val) != str(new_val):
            # Record audit history
            db.add(TaskHistory(
                task_id=task.id,
                field_changed=field,
                old_value=str(old_val) if old_val is not None else None,
                new_value=str(new_val) if new_val is not None else None,
                note=note or f"Updated {field}"
            ))
            setattr(task, field, new_val)

    db.commit()
    db.refresh(task)
    return task
