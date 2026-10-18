import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

# Base schemas
class SpeakerBase(BaseModel):
    original_label: str
    display_name: str
    role: Optional[str] = None

class SpeakerUpdate(BaseModel):
    display_name: str
    role: Optional[str] = None

class SpeakerRead(SpeakerBase):
    id: int
    meeting_id: int
    class Config:
        from_attributes = True

class TranscriptSegmentRead(BaseModel):
    id: int
    meeting_id: int
    speaker_label: str
    start_time: float
    end_time: float
    text: str
    confidence: float
    class Config:
        from_attributes = True

class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    owner: str = "Unassigned"
    deadline_text: Optional[str] = None
    deadline_normalized: Optional[datetime.datetime] = None
    deadline_status: str = "Exact" # Exact, Ambiguous, Not specified
    status: str = "Pending" # Pending, In Progress, Blocked, Completed, Overdue, Needs Clarification, Cancelled
    priority: str = "Medium" # Low, Medium, High, Critical
    confidence: float = 0.9
    evidence_quote: Optional[str] = None
    evidence_timestamp: Optional[float] = None
    evidence_segment_id: Optional[int] = None

class TaskCreate(TaskBase):
    meeting_id: int
    project_id: Optional[int] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    deadline_text: Optional[str] = None
    deadline_normalized: Optional[datetime.datetime] = None
    deadline_status: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    note: Optional[str] = None

class TaskHistoryRead(BaseModel):
    id: int
    task_id: int
    field_changed: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime.datetime
    class Config:
        from_attributes = True

class TaskRead(TaskBase):
    id: int
    meeting_id: int
    project_id: Optional[int] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    history: List[TaskHistoryRead] = []
    class Config:
        from_attributes = True

class DecisionBase(BaseModel):
    topic: Optional[str] = None
    decision: str
    status: str = "Final" # Final, Tentative, Undecided, Rejected
    participants: Optional[str] = None
    evidence_quote: Optional[str] = None
    evidence_timestamp: Optional[float] = None
    confidence: float = 0.9
    supersedes_previous_decision: bool = False
    previous_decision_id: Optional[int] = None
    drift_reason: Optional[str] = None

class DecisionRead(DecisionBase):
    id: int
    meeting_id: int
    project_id: Optional[int] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    class Config:
        from_attributes = True

class ConflictRead(BaseModel):
    id: int
    meeting_id: int
    topic: str
    statement_a: str
    speaker_a: Optional[str] = None
    timestamp_a: Optional[float] = None
    statement_b: str
    speaker_b: Optional[str] = None
    timestamp_b: Optional[float] = None
    status: str # Needs confirmation, Resolved, Dismissed
    resolution: Optional[str] = None
    created_at: datetime.datetime
    class Config:
        from_attributes = True

class QuestionRead(BaseModel):
    id: int
    meeting_id: int
    question: str
    asked_by: Optional[str] = None
    status: str # Unresolved, Answered, Deferred
    answer: Optional[str] = None
    evidence_quote: Optional[str] = None
    evidence_timestamp: Optional[float] = None
    created_at: datetime.datetime
    class Config:
        from_attributes = True

class DependencyRead(BaseModel):
    id: int
    meeting_id: int
    source_item_type: str
    source_item_id: Optional[int] = None
    source_label: str
    target_item_type: str
    target_item_id: Optional[int] = None
    target_label: str
    relation_type: str
    evidence_quote: Optional[str] = None
    evidence_timestamp: Optional[float] = None
    class Config:
        from_attributes = True

class EntityRead(BaseModel):
    id: int
    meeting_id: int
    text: str
    label: str
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    evidence_timestamp: Optional[float] = None
    class Config:
        from_attributes = True

# Meeting Schemas
class MeetingCreate(BaseModel):
    title: str
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    agenda: Optional[str] = None
    language: str = "en"
    participants: Optional[str] = None # comma separated names
    meeting_date: Optional[datetime.datetime] = None

class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    agenda: Optional[str] = None
    project_id: Optional[int] = None

class MediaValidationResponse(BaseModel):
    valid: bool
    status: str # valid, warning, error
    message: str
    video_detected: bool = False
    audio_detected: bool = False
    video_duration: float = 0.0
    audio_duration: float = 0.0
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    mode: str = "single" # paired or single

class MeetingListRead(BaseModel):
    id: int
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    title: str
    meeting_date: datetime.datetime
    duration_seconds: float
    status: str
    processing_step: Optional[str] = None
    media_type: str
    audio_source: Optional[str] = None
    video_source: Optional[str] = None
    external_audio_name: Optional[str] = None
    video_duration: Optional[float] = 0.0
    audio_duration: Optional[float] = 0.0
    media_validation_status: Optional[str] = "valid"
    actionability_score: float
    created_at: datetime.datetime
    task_count: int = 0
    decision_count: int = 0
    conflict_count: int = 0
    class Config:
        from_attributes = True

class MeetingDetailRead(BaseModel):
    id: int
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    title: str
    meeting_date: datetime.datetime
    duration_seconds: float
    agenda: Optional[str] = None
    media_path: Optional[str] = None
    media_type: str
    video_path: Optional[str] = None
    audio_path: Optional[str] = None
    playback_path: Optional[str] = None
    audio_source: Optional[str] = None
    video_source: Optional[str] = None
    external_audio_name: Optional[str] = None
    video_duration: Optional[float] = 0.0
    audio_duration: Optional[float] = 0.0
    media_validation_status: Optional[str] = "valid"
    media_validation_message: Optional[str] = None
    status: str
    processing_step: Optional[str] = None
    error_message: Optional[str] = None
    language: str
    actionability_score: float
    summary: Optional[str] = None
    mom_json: Optional[Dict[str, Any]] = None
    ai_provider: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    speakers: List[SpeakerRead] = []
    segments: List[TranscriptSegmentRead] = []
    tasks: List[TaskRead] = []
    decisions: List[DecisionRead] = []
    conflicts: List[ConflictRead] = []
    questions: List[QuestionRead] = []
    dependencies: List[DependencyRead] = []
    entities: List[EntityRead] = []
    class Config:
        from_attributes = True

# Project Schemas
class ProjectRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    meeting_count: int = 0
    task_count: int = 0
    health_status: str = "Healthy" # Healthy, At Risk, Critical
    class Config:
        from_attributes = True

# Workflow graph schema
class WorkflowNode(BaseModel):
    id: str
    type: str # taskNode, decisionNode, blockerNode, questionNode
    data: Dict[str, Any]
    position: Dict[str, float]

class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str
    label: Optional[str] = None
    animated: Optional[bool] = False
    style: Optional[Dict[str, Any]] = None

class WorkflowGraph(BaseModel):
    nodes: List[WorkflowNode]
    edges: List[WorkflowEdge]

# Ask the meeting
class AskMeetingRequest(BaseModel):
    question: str

class EvidenceItem(BaseModel):
    timestamp: float
    speaker: str
    quote: str

class AskMeetingResponse(BaseModel):
    answer: str
    evidence: List[EvidenceItem] = []
    grounded_in: List[str] = [] # "transcript", "tasks", "decisions"

# NLP Evaluation
class EvaluationMetric(BaseModel):
    task_f1: float
    task_precision: float
    task_recall: float
    entity_f1: float
    decision_f1: float
    deadline_accuracy: float
    relation_f1: float
    overall_score: float

class EvaluationComparison(BaseModel):
    rule_based: EvaluationMetric
    transformer: EvaluationMetric
    hybrid_llm: EvaluationMetric
    test_cases_count: int
