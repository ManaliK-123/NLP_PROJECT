from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Project, Meeting, Task
from app.schemas.schemas import ProjectRead
from app.services.project_memory import get_project_memory_intelligence

router = APIRouter(prefix="/api/projects", tags=["projects"])

@router.get("", response_model=List[ProjectRead])
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).all()
    results = []
    for p in projects:
        m_count = len(p.meetings)
        t_count = len(p.tasks)
        has_blocked = any(t.status == "Blocked" for t in p.tasks)
        health = "At Risk" if has_blocked else "Healthy"
        results.append(ProjectRead(
            id=p.id,
            name=p.name,
            description=p.description,
            created_at=p.created_at,
            updated_at=p.updated_at,
            meeting_count=m_count,
            task_count=t_count,
            health_status=health
        ))
    return results

@router.post("", response_model=ProjectRead)
def create_project(name: str, description: Optional[str] = None, db: Session = Depends(get_db)):
    existing = db.query(Project).filter(Project.name == name.strip()).first()
    if existing:
        return existing
    proj = Project(name=name.strip(), description=description)
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return proj

@router.get("/{id}/memory")
def get_project_memory(id: int, db: Session = Depends(get_db)):
    intel = get_project_memory_intelligence(db, id)
    if "error" in intel:
        raise HTTPException(status_code=404, detail=intel["error"])
    return intel
