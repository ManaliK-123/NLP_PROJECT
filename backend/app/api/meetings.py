import os
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models.models import Meeting, Project, Speaker, TranscriptSegment, Task, Decision, Conflict, Question, Dependency, Entity
from app.media.processor import validate_media_pair
from app.schemas.schemas import (
    MeetingCreate, MeetingUpdate, MeetingListRead, MeetingDetailRead,
    TranscriptSegmentRead, WorkflowGraph, AskMeetingRequest, AskMeetingResponse, SpeakerUpdate, SpeakerRead,
    MediaValidationResponse
)
from app.services.meeting_service import process_meeting_pipeline
from app.workflow.generator import generate_workflow_graph
from app.services.qa_assistant import ask_meeting_assistant
from app.services.mom_generator import generate_mom_markdown
from app.services.export_service import export_mom_csv, export_mom_pdf

router = APIRouter(prefix="/api/meetings", tags=["meetings"])

@router.get("", response_model=List[MeetingListRead])
def list_meetings(db: Session = Depends(get_db)):
    meetings = db.query(Meeting).order_by(Meeting.meeting_date.desc()).all()
    results = []
    for m in meetings:
        proj_name = m.project.name if m.project else None
        results.append(MeetingListRead(
            id=m.id,
            project_id=m.project_id,
            project_name=proj_name,
            title=m.title,
            meeting_date=m.meeting_date,
            duration_seconds=m.duration_seconds,
            status=m.status,
            processing_step=m.processing_step,
            media_type=m.media_type,
            audio_source=m.audio_source,
            video_source=m.video_source,
            external_audio_name=m.external_audio_name,
            video_duration=m.video_duration or 0.0,
            audio_duration=m.audio_duration or 0.0,
            media_validation_status=m.media_validation_status or "valid",
            actionability_score=m.actionability_score,
            created_at=m.created_at,
            task_count=len(m.tasks),
            decision_count=len(m.decisions),
            conflict_count=len(m.conflicts)
        ))
    return results

@router.post("/validate-media", response_model=MediaValidationResponse)
async def validate_media_endpoint(
    video_file: Optional[UploadFile] = File(None),
    audio_file: Optional[UploadFile] = File(None)
):
    """
    Validate uploaded media before committing to database.
    Checks codecs, formats, and detects duration mismatch safely.
    """
    temp_dir = settings.UPLOAD_DIR / "temp_validation"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    temp_v = None
    temp_a = None
    try:
        if video_file and video_file.filename:
            v_ext = Path(video_file.filename).suffix.lower()
            temp_v = temp_dir / f"temp_vid_{os.urandom(4).hex()}{v_ext}"
            with open(temp_v, "wb") as f:
                shutil.copyfileobj(video_file.file, f)
                
        if audio_file and audio_file.filename:
            a_ext = Path(audio_file.filename).suffix.lower()
            temp_a = temp_dir / f"temp_aud_{os.urandom(4).hex()}{a_ext}"
            with open(temp_a, "wb") as f:
                shutil.copyfileobj(audio_file.file, f)
                
        res = validate_media_pair(temp_v, temp_a)
        return MediaValidationResponse(**res)
    finally:
        if temp_v and temp_v.exists():
            try: os.remove(temp_v)
            except Exception: pass
        if temp_a and temp_a.exists():
            try: os.remove(temp_a)
            except Exception: pass

@router.post("", response_model=MeetingDetailRead)
def create_meeting(payload: MeetingCreate, db: Session = Depends(get_db)):
    project_id = payload.project_id
    if not project_id and payload.project_name:
        proj = db.query(Project).filter(Project.name == payload.project_name.strip()).first()
        if not proj:
            proj = Project(name=payload.project_name.strip())
            db.add(proj)
            db.commit()
            db.refresh(proj)
        project_id = proj.id

    meeting = Meeting(
        title=payload.title,
        project_id=project_id,
        agenda=payload.agenda,
        language=payload.language,
        status="pending",
        processing_step="Media awaiting upload"
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    # If participants provided, create placeholder speakers
    if payload.participants:
        for p in payload.participants.split(","):
            p_clean = p.strip()
            if p_clean:
                db.add(Speaker(meeting_id=meeting.id, original_label=p_clean, display_name=p_clean, role="Participant"))
        db.commit()

    return meeting

@router.get("/{id}", response_model=MeetingDetailRead)
def get_meeting(id: int, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting

@router.post("/{id}/upload")
async def upload_meeting_media(
    id: int,
    video_file: Optional[UploadFile] = File(None),
    audio_file: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    auto_process: bool = True,
    db: Session = Depends(get_db)
):
    """
    Handle Mode A (Paired video + external audio) and Mode B (Single media).
    """
    meeting = db.query(Meeting).filter(Meeting.id == id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Fallback to single file if video_file and audio_file are not specified
    if not video_file and not audio_file and file:
        f_ext = Path(file.filename).suffix.lower() if file.filename else ".mp4"
        is_audio = f_ext in [".mp3", ".wav", ".m4a", ".ogg", ".aac"]
        if is_audio:
            audio_file = file
        else:
            video_file = file

    if not video_file and not audio_file:
        raise HTTPException(status_code=400, detail="No media files uploaded.")

    # Save video file
    if video_file and video_file.filename:
        v_ext = Path(video_file.filename).suffix.lower()
        saved_vid_name = f"meeting_{id}_video{v_ext}"
        saved_vid_path = settings.UPLOAD_DIR / saved_vid_name
        with open(saved_vid_path, "wb") as f:
            shutil.copyfileobj(video_file.file, f)
        meeting.video_path = str(saved_vid_path)
        meeting.video_source = video_file.filename
        meeting.media_path = str(saved_vid_path)
        meeting.media_type = "video"

    # Save external audio file
    if audio_file and audio_file.filename:
        a_ext = Path(audio_file.filename).suffix.lower()
        saved_aud_name = f"meeting_{id}_external_audio{a_ext}"
        saved_aud_path = settings.UPLOAD_DIR / saved_aud_name
        with open(saved_aud_path, "wb") as f:
            shutil.copyfileobj(audio_file.file, f)
        meeting.audio_path = str(saved_aud_path)
        meeting.external_audio_name = audio_file.filename
        meeting.audio_source = "External Audio Source (WAV)"
        if not meeting.media_path:
            meeting.media_path = str(saved_aud_path)
            meeting.media_type = "audio"

    meeting.status = "uploaded"
    meeting.processing_step = "Media uploaded, queued for pipeline execution..."
    db.commit()

    if auto_process:
        background_tasks.add_task(process_meeting_pipeline, db, id)

    return {
        "success": True,
        "message": "Media uploaded successfully",
        "video_source": meeting.video_source,
        "audio_source": meeting.audio_source,
        "status": meeting.status
    }

@router.post("/{id}/process")
def trigger_processing(
    id: int,
    background_tasks: BackgroundTasks,
    sync: bool = False,
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if sync:
        process_meeting_pipeline(db, id)
        db.refresh(meeting)
        return {"success": True, "message": "Processing completed synchronously", "status": meeting.status}
    else:
        background_tasks.add_task(process_meeting_pipeline, db, id)
        return {"success": True, "message": "Processing started in background", "status": "processing"}

@router.get("/{id}/transcript", response_model=List[TranscriptSegmentRead])
def get_meeting_transcript(id: int, db: Session = Depends(get_db)):
    segments = db.query(TranscriptSegment).filter(TranscriptSegment.meeting_id == id).order_by(TranscriptSegment.start_time.asc()).all()
    return segments

@router.get("/{id}/workflow", response_model=WorkflowGraph)
def get_meeting_workflow(id: int, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    tasks = [t.__dict__ for t in meeting.tasks]
    decisions = [d.__dict__ for d in meeting.decisions]
    conflicts = [c.__dict__ for c in meeting.conflicts]
    dependencies = [dep.__dict__ for dep in meeting.dependencies]

    graph = generate_workflow_graph(tasks, decisions, conflicts, dependencies)
    return graph

@router.get("/{id}/mom")
def get_meeting_mom(id: int, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if not meeting.mom_json:
        raise HTTPException(status_code=400, detail="MOM not generated yet for this meeting")
    return meeting.mom_json

@router.get("/{id}/export/{format}")
def export_meeting(id: int, format: str, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == id).first()
    if not meeting or not meeting.mom_json:
        raise HTTPException(status_code=404, detail="Meeting or MOM not available")

    fmt = format.lower()
    if fmt == "json":
        return meeting.mom_json
    elif fmt == "markdown" or fmt == "md":
        md_text = generate_mom_markdown(meeting.mom_json)
        return Response(content=md_text, media_type="text/markdown", headers={"Content-Disposition": f"attachment; filename=meeting_{id}_mom.md"})
    elif fmt == "csv":
        csv_text = export_mom_csv(meeting.mom_json)
        return Response(content=csv_text, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=meeting_{id}_actions.csv"})
    elif fmt == "pdf":
        pdf_bytes = export_mom_pdf(meeting.mom_json)
        return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=meeting_{id}_mom.pdf"})
    else:
        raise HTTPException(status_code=400, detail="Supported export formats: json, markdown, csv, pdf")

@router.post("/{id}/ask", response_model=AskMeetingResponse)
def ask_meeting(id: int, payload: AskMeetingRequest, db: Session = Depends(get_db)):
    result = ask_meeting_assistant(db, id, payload.question)
    return result

@router.patch("/{id}/speakers/{speaker_id}", response_model=SpeakerRead)
def update_speaker_name(id: int, speaker_id: int, payload: SpeakerUpdate, db: Session = Depends(get_db)):
    speaker = db.query(Speaker).filter(Speaker.id == speaker_id, Speaker.meeting_id == id).first()
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")

    old_label = speaker.original_label
    new_name = payload.display_name.strip()
    speaker.display_name = new_name
    if payload.role:
        speaker.role = payload.role

    # Also update transcript segments matching this speaker label
    db.query(TranscriptSegment).filter(
        TranscriptSegment.meeting_id == id,
        TranscriptSegment.speaker_label == old_label
    ).update({"speaker_label": new_name})

    db.commit()
    db.refresh(speaker)
    return speaker

@router.get("/{id}/media")
def stream_media(id: int, db: Session = Depends(get_db)):
    meeting = db.query(Meeting).filter(Meeting.id == id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
        
    media_file = (
        meeting.playback_path or
        meeting.video_path or
        meeting.media_path or
        meeting.audio_path
    )
    if not media_file or not os.path.exists(media_file):
        raise HTTPException(status_code=404, detail="Media file not found")
        
    return FileResponse(media_file)
