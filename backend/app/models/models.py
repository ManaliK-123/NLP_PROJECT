import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey, Table, JSON
)
from sqlalchemy.orm import relationship
from app.database import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    meetings = relationship("Meeting", back_populates="project", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="project")
    decisions = relationship("Decision", back_populates="project")


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False, index=True)
    meeting_date = Column(DateTime, default=datetime.datetime.utcnow)
    duration_seconds = Column(Float, default=0.0)
    agenda = Column(Text, nullable=True)
    media_path = Column(String(512), nullable=True)
    media_type = Column(String(50), default="video") # video or audio
    video_path = Column(String(512), nullable=True)
    audio_path = Column(String(512), nullable=True)
    playback_path = Column(String(512), nullable=True)
    audio_source = Column(String(100), default="extracted_video_audio") # external_headset_wav, extracted_video_audio, synthesized_demo_audio
    video_source = Column(String(255), nullable=True)
    external_audio_name = Column(String(255), nullable=True)
    video_duration = Column(Float, default=0.0)
    audio_duration = Column(Float, default=0.0)
    media_validation_status = Column(String(50), default="valid") # valid, warning, error
    media_validation_message = Column(Text, nullable=True)
    status = Column(String(50), default="pending") # pending, processing, completed, error
    processing_step = Column(String(100), default="Initialized")
    error_message = Column(Text, nullable=True)
    language = Column(String(20), default="en")
    actionability_score = Column(Float, default=0.0)
    summary = Column(Text, nullable=True)
    mom_json = Column(JSON, nullable=True)
    ai_provider = Column(String(50), default="local")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    project = relationship("Project", back_populates="meetings")
    speakers = relationship("Speaker", back_populates="meeting", cascade="all, delete-orphan")
    segments = relationship("TranscriptSegment", back_populates="meeting", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="meeting", cascade="all, delete-orphan")
    decisions = relationship("Decision", back_populates="meeting", cascade="all, delete-orphan")
    conflicts = relationship("Conflict", back_populates="meeting", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="meeting", cascade="all, delete-orphan")
    entities = relationship("Entity", back_populates="meeting", cascade="all, delete-orphan")
    dependencies = relationship("Dependency", back_populates="meeting", cascade="all, delete-orphan")


class Speaker(Base):
    __tablename__ = "speakers"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    original_label = Column(String(50), nullable=False) # e.g. SPEAKER_00, Speaker 1
    display_name = Column(String(100), nullable=False) # e.g. Rahul
    role = Column(String(100), nullable=True)

    meeting = relationship("Meeting", back_populates="speakers")


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    speaker_label = Column(String(100), nullable=False)
    start_time = Column(Float, nullable=False, index=True)
    end_time = Column(Float, nullable=False)
    text = Column(Text, nullable=False)
    confidence = Column(Float, default=1.0)

    meeting = relationship("Meeting", back_populates="segments")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    owner = Column(String(100), default="Unassigned")
    deadline_text = Column(String(100), nullable=True)
    deadline_normalized = Column(DateTime, nullable=True)
    deadline_status = Column(String(50), default="Exact") # Exact, Ambiguous, Not specified
    status = Column(String(50), default="Pending") # Pending, In Progress, Blocked, Completed, Overdue, Needs Clarification, Cancelled
    priority = Column(String(50), default="Medium") # Low, Medium, High, Critical
    confidence = Column(Float, default=0.9)
    evidence_quote = Column(Text, nullable=True)
    evidence_timestamp = Column(Float, nullable=True)
    evidence_segment_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    meeting = relationship("Meeting", back_populates="tasks")
    project = relationship("Project", back_populates="tasks")
    history = relationship("TaskHistory", back_populates="task", cascade="all, delete-orphan")


class TaskHistory(Base):
    __tablename__ = "task_history"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    field_changed = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    task = relationship("Task", back_populates="history")


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    topic = Column(String(255), nullable=True)
    decision = Column(Text, nullable=False)
    status = Column(String(50), default="Final") # Final, Tentative, Undecided, Rejected
    participants = Column(String(255), nullable=True)
    evidence_quote = Column(Text, nullable=True)
    evidence_timestamp = Column(Float, nullable=True)
    confidence = Column(Float, default=0.9)
    supersedes_previous_decision = Column(Boolean, default=False)
    previous_decision_id = Column(Integer, nullable=True)
    drift_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    meeting = relationship("Meeting", back_populates="decisions")
    project = relationship("Project", back_populates="decisions")
    history = relationship("DecisionHistory", back_populates="decision_ref", cascade="all, delete-orphan")


class DecisionHistory(Base):
    __tablename__ = "decision_history"

    id = Column(Integer, primary_key=True, index=True)
    decision_id = Column(Integer, ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False)
    change_type = Column(String(100), default="Update") # Created, Drift, Superseded, Revoked
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    decision_ref = relationship("Decision", back_populates="history")


class Conflict(Base):
    __tablename__ = "conflicts"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    topic = Column(String(255), nullable=False)
    statement_a = Column(Text, nullable=False)
    speaker_a = Column(String(100), nullable=True)
    timestamp_a = Column(Float, nullable=True)
    statement_b = Column(Text, nullable=False)
    speaker_b = Column(String(100), nullable=True)
    timestamp_b = Column(Float, nullable=True)
    status = Column(String(50), default="Needs confirmation") # Needs confirmation, Resolved, Dismissed
    resolution = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    meeting = relationship("Meeting", back_populates="conflicts")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    question = Column(Text, nullable=False)
    asked_by = Column(String(100), nullable=True)
    status = Column(String(50), default="Unresolved") # Unresolved, Answered, Deferred
    answer = Column(Text, nullable=True)
    evidence_quote = Column(Text, nullable=True)
    evidence_timestamp = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    meeting = relationship("Meeting", back_populates="questions")


class Dependency(Base):
    __tablename__ = "dependencies"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    source_item_type = Column(String(50), default="task") # task, decision, milestone
    source_item_id = Column(Integer, nullable=True)
    source_label = Column(String(255), nullable=False)
    target_item_type = Column(String(50), default="task")
    target_item_id = Column(Integer, nullable=True)
    target_label = Column(String(255), nullable=False)
    relation_type = Column(String(50), default="blocks") # blocks, depends_on, follows, resolves
    evidence_quote = Column(Text, nullable=True)
    evidence_timestamp = Column(Float, nullable=True)

    meeting = relationship("Meeting", back_populates="dependencies")


class Entity(Base):
    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(String(255), nullable=False)
    label = Column(String(50), nullable=False) # PERSON, DATE, ORG, TECH, TOOL, MILESTONE
    start_char = Column(Integer, nullable=True)
    end_char = Column(Integer, nullable=True)
    evidence_timestamp = Column(Float, nullable=True)

    meeting = relationship("Meeting", back_populates="entities")
