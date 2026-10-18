import os
import shutil
import datetime
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import (
    Project, Meeting, Speaker, TranscriptSegment, Task, TaskHistory,
    Decision, DecisionHistory, Conflict, Question, Dependency, Entity
)
from app.media.processor import (
    validate_media_file, extract_and_convert_audio, get_audio_duration,
    validate_media_pair, prepare_playback_media, inspect_media
)
from app.nlp.transcriber import transcribe_audio, generate_fallback_transcript
from app.nlp.extraction import extract_all_meeting_intelligence
from app.workflow.generator import generate_workflow_graph
from app.services.mom_generator import build_mom_document
from app.services.execution_radar import calculate_execution_radar
from app.llm.provider import llm_provider

logger = logging.getLogger(__name__)

def seed_demo_data_if_empty(db: Session):
    """
    Ensure the database is seeded with the rich Demo Meeting and Project Memory
    so the system is immediately usable upon first launch.
    """
    # Check if demo project exists
    demo_proj = db.query(Project).filter(Project.name == "Autonomous Driving NLP Assistant").first()
    if not demo_proj:
        demo_proj = Project(
            name="Autonomous Driving NLP Assistant",
            description="End-to-end multimodal perception and instruction execution system for autonomous mobility."
        )
        db.add(demo_proj)
        db.commit()
        db.refresh(demo_proj)

    # Check if demo meeting exists
    existing_meeting = db.query(Meeting).filter(Meeting.title == "Sprint Planning & Architecture Sync #14").first()
    if existing_meeting:
        return existing_meeting

    # Create Demo Meeting
    ref_time = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    demo_wav_path = settings.UPLOAD_DIR / "demo_meeting.wav"
    demo_meeting = Meeting(
        project_id=demo_proj.id,
        title="Sprint Planning & Architecture Sync #14",
        meeting_date=ref_time,
        duration_seconds=28.5,
        agenda="Sprint deliverables, dataset labeling, model architecture decision, and report timeline",
        media_type="audio",
        media_path=str(demo_wav_path) if demo_wav_path.exists() else None,
        status="completed",
        processing_step="Analysis completed",
        language="en",
        actionability_score=78.5,
        ai_provider="Local NLP Engine (Zero-Friction Offline)",
        summary="Sprint alignment covering dataset completion by Rahul, baseline model training by Priya, open architecture questions, and clarification of report deadline discrepancy."
    )
    db.add(demo_meeting)
    db.commit()
    db.refresh(demo_meeting)

    # Add Speakers
    speakers_data = [
        {"original_label": "Speaker 1", "display_name": "Alex", "role": "Lead / Moderator"},
        {"original_label": "Speaker 2", "display_name": "Rahul", "role": "Data Engineer"},
        {"original_label": "Speaker 3", "display_name": "Priya", "role": "ML Engineer"}
    ]
    for s_info in speakers_data:
        spk = Speaker(
            meeting_id=demo_meeting.id,
            original_label=s_info["original_label"],
            display_name=s_info["display_name"],
            role=s_info["role"]
        )
        db.add(spk)
    db.commit()

    # Add Transcript Segments
    demo_segments = [
        {"start_time": 0.0, "end_time": 3.4, "speaker_label": "Alex", "text": "Alright team, let's start the sync. Rahul, complete the dataset by Wednesday.", "confidence": 0.98},
        {"start_time": 3.8, "end_time": 7.5, "speaker_label": "Rahul", "text": "Sure, I'll clean the labels and push to the repo. After that, Priya will train the baseline model.", "confidence": 0.96},
        {"start_time": 7.9, "end_time": 11.2, "speaker_label": "Priya", "text": "Yes, I will take care of model training once Rahul finishes preprocessing.", "confidence": 0.95},
        {"start_time": 11.6, "end_time": 15.0, "speaker_label": "Alex", "text": "We haven't decided which architecture to use for the classifier.", "confidence": 0.94},
        {"start_time": 15.3, "end_time": 19.1, "speaker_label": "Rahul", "text": "Let's discuss that in Friday's meeting with the professor.", "confidence": 0.93},
        {"start_time": 19.5, "end_time": 24.0, "speaker_label": "Priya", "text": "Wait, actually, the report submission is Thursday, not Friday.", "confidence": 0.97},
        {"start_time": 24.5, "end_time": 28.2, "speaker_label": "Alex", "text": "Good catch! Someone should update the project documentation right away.", "confidence": 0.91}
    ]

    saved_segs = []
    for seg in demo_segments:
        s_obj = TranscriptSegment(
            meeting_id=demo_meeting.id,
            speaker_label=seg["speaker_label"],
            start_time=seg["start_time"],
            end_time=seg["end_time"],
            text=seg["text"],
            confidence=seg["confidence"]
        )
        db.add(s_obj)
        saved_segs.append(s_obj)
    db.commit()

    # Add Tasks
    # Wednesday date
    wednesday_dt = ref_time + datetime.timedelta(days=2)
    task1 = Task(
        meeting_id=demo_meeting.id,
        project_id=demo_proj.id,
        title="Complete dataset preprocessing & label cleaning",
        description="Clean dataset labels and push to project repository",
        owner="Rahul",
        deadline_text="Wednesday",
        deadline_normalized=wednesday_dt,
        deadline_status="Exact",
        status="In Progress",
        priority="High",
        confidence=0.98,
        evidence_quote="Rahul, complete the dataset by Wednesday.",
        evidence_timestamp=0.0,
        evidence_segment_id=saved_segs[0].id
    )
    task2 = Task(
        meeting_id=demo_meeting.id,
        project_id=demo_proj.id,
        title="Train baseline model",
        description="Run initial model training on preprocessed dataset",
        owner="Priya",
        deadline_text="After dataset completion",
        deadline_normalized=wednesday_dt + datetime.timedelta(days=1),
        deadline_status="Ambiguous",
        status="Blocked",
        priority="High",
        confidence=0.96,
        evidence_quote="After that, Priya will train the baseline model.",
        evidence_timestamp=3.8,
        evidence_segment_id=saved_segs[1].id
    )

    task3 = Task(
        meeting_id=demo_meeting.id,
        project_id=demo_proj.id,
        title="Update project documentation",
        description="Update repo docs with revised schedule and deliverables",
        owner="Unassigned",
        deadline_text="ASAP",
        deadline_normalized=None,
        deadline_status="Ambiguous",
        status="Needs Clarification",
        priority="Medium",
        confidence=0.85,
        evidence_quote="Someone should update the project documentation right away.",
        evidence_timestamp=24.5,
        evidence_segment_id=saved_segs[6].id
    )
    db.add_all([task1, task2, task3])
    db.commit()

    # Add Task History
    db.add(TaskHistory(task_id=task1.id, field_changed="status", old_value="Pending", new_value="In Progress", note="Rahul began label cleaning"))
    db.commit()

    # Add Decisions
    dec1 = Decision(
        meeting_id=demo_meeting.id,
        project_id=demo_proj.id,
        topic="Model Architecture Selection",
        decision="We haven't decided which architecture to use for the classifier.",
        status="Undecided",
        participants="Alex, Rahul, Priya",
        evidence_quote="We haven't decided which architecture to use for the classifier.",
        evidence_timestamp=11.6,
        confidence=0.94,
        supersedes_previous_decision=False
    )
    db.add(dec1)
    db.commit()

    # Add Conflict
    conf1 = Conflict(
        meeting_id=demo_meeting.id,
        topic="Report Submission Deadline Discrepancy",
        statement_a="Let's discuss that in Friday's meeting with the professor.",
        speaker_a="Rahul",
        timestamp_a=15.3,
        statement_b="Wait, actually, the report submission is Thursday, not Friday.",
        speaker_b="Priya",
        timestamp_b=19.5,
        status="Needs confirmation",
        resolution="Confirmation required: Thursday deadline takes precedence unless professor extends to Friday."
    )
    db.add(conf1)

    # Add Dependency
    dep1 = Dependency(
        meeting_id=demo_meeting.id,
        source_item_type="task",
        source_label=task1.title,
        target_item_type="task",
        target_label=task2.title,
        relation_type="blocks",
        evidence_quote="After that, Priya will train the baseline model.",
        evidence_timestamp=3.8
    )
    db.add(dep1)

    # Add Entities
    for ent_data in [
        {"text": "Rahul", "label": "PERSON", "evidence_timestamp": 0.0},
        {"text": "Priya", "label": "PERSON", "evidence_timestamp": 3.8},
        {"text": "Alex", "label": "PERSON", "evidence_timestamp": 0.0},
        {"text": "Wednesday", "label": "DATE", "evidence_timestamp": 0.0},
        {"text": "Thursday", "label": "DATE", "evidence_timestamp": 19.5},
        {"text": "Friday", "label": "DATE", "evidence_timestamp": 15.3}
    ]:
        db.add(Entity(meeting_id=demo_meeting.id, **ent_data))

    # Add MOM
    mom_payload = build_mom_document(
        meeting_title=demo_meeting.title,
        meeting_date=demo_meeting.meeting_date,
        duration_seconds=demo_meeting.duration_seconds,
        agenda=demo_meeting.agenda,
        participants=["Alex", "Rahul", "Priya"],
        summary=demo_meeting.summary,
        tasks=[t.__dict__ for t in [task1, task2, task3]],
        decisions=[d.__dict__ for d in [dec1]],
        conflicts=[conf1.__dict__],
        questions=[],
        dependencies=[dep1.__dict__]
    )
    demo_meeting.mom_json = mom_payload
    db.commit()

    # Create a secondary prior meeting in the same project to showcase Decision Drift & Project Memory!
    prior_meeting = Meeting(
        project_id=demo_proj.id,
        title="Kickoff & Data Strategy Sync #12",
        meeting_date=ref_time - datetime.timedelta(days=7),
        duration_seconds=35.0,
        agenda="Initial dataset exploration and framework agreement",
        media_type="audio",
        status="completed",
        processing_step="Analysis completed",
        actionability_score=85.0,
        ai_provider="Local NLP Engine",
        summary="Agreed to tentatively use Dataset A for initial exploration."
    )
    db.add(prior_meeting)
    db.commit()
    db.refresh(prior_meeting)

    # Prior decision that later drifted
    prior_dec = Decision(
        meeting_id=prior_meeting.id,
        project_id=demo_proj.id,
        topic="Dataset Selection",
        decision="We agreed to use Dataset A for training.",
        status="Final",
        participants="Alex, Rahul",
        evidence_quote="We agreed to use Dataset A for training.",
        evidence_timestamp=5.0,
        confidence=0.95
    )
    db.add(prior_dec)
    db.commit()
    db.refresh(prior_dec)
    
    # Drifted decision in latest meeting:
    drifted_dec = Decision(
        meeting_id=demo_meeting.id,
        project_id=demo_proj.id,
        topic="Dataset Selection",
        decision="We are now cleaning expanded benchmark labels instead of raw Dataset A.",
        status="Final",
        participants="Rahul",
        evidence_quote="Sure, I'll clean the labels and push to the repo.",
        evidence_timestamp=3.8,
        confidence=0.92,
        supersedes_previous_decision=True,
        previous_decision_id=prior_dec.id,
        drift_reason="Shifted from raw Dataset A to cleaned multi-source benchmark for robust generalization."
    )
    db.add(drifted_dec)
    db.commit()

    logger.info("Database successfully seeded with demo meeting and cross-meeting project memory.")
    return demo_meeting


def process_meeting_pipeline(db: Session, meeting_id: int):
    """
    Execute full asynchronous/background meeting processing pipeline:
    1. Validate media
    2. Extract audio with FFmpeg
    3. Transcribe speech with faster-whisper (or fallback)
    4. Speaker identification
    5. Entity extraction
    6. Task & ambiguity detection
    7. Decision & drift detection
    8. Conflict & contradiction detection
    9. Dependency graph mapping
    10. Generate MOM & Workflow
    11. Update project execution memory
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        logger.error(f"Meeting {meeting_id} not found for processing.")
        return

    try:
        meeting.status = "processing"
        meeting.processing_step = "Validating media file..."
        db.commit()

        # Determine video and audio paths
        video_path = Path(meeting.video_path) if meeting.video_path else None
        audio_path = Path(meeting.audio_path) if meeting.audio_path else None
        media_path = Path(meeting.media_path) if meeting.media_path else None

        if not video_path and media_path and meeting.media_type == "video":
            video_path = media_path
        if not audio_path and media_path and meeting.media_type == "audio":
            audio_path = media_path

        # 1. Media Validation (Mode A / Mode B)
        validation = validate_media_pair(video_path, audio_path)
        meeting.media_validation_status = validation["status"]
        meeting.media_validation_message = validation["message"]
        meeting.video_duration = validation.get("video_duration", 0.0)
        meeting.audio_duration = validation.get("audio_duration", 0.0)

        if not validation["valid"]:
            meeting.status = "error"
            meeting.error_message = validation["message"]
            meeting.processing_step = f"Validation failed: {validation['message']}"
            db.commit()
            logger.error(f"Media validation error for meeting {meeting_id}: {validation['message']}")
            return

        wav_path = None
        duration = max(meeting.video_duration or 0.0, meeting.audio_duration or 0.0)

        # MODE A: Paired media - Separate external audio provided
        if audio_path and audio_path.exists():
            meeting.processing_step = "Processing external audio (preferred ASR source)..."
            db.commit()

            asr_wav = settings.OUTPUT_DIR / f"meeting_{meeting_id}_audio.wav"
            success, dur, err = extract_and_convert_audio(audio_path, asr_wav)
            if success:
                wav_path = asr_wav
                if dur > 0:
                    meeting.audio_duration = dur
                    duration = max(duration, dur)
            else:
                wav_path = audio_path

            if not meeting.audio_source or meeting.audio_source == "extracted_video_audio":
                meeting.audio_source = "External Headset Audio (WAV)" if "headset" in audio_path.name.lower() else "External Audio Source (WAV)"

            # Prepare web-playable MP4 for browser video player
            if video_path and video_path.exists():
                playback_target = settings.UPLOAD_DIR / f"meeting_{meeting_id}_web_playback.mp4"
                playback_res = prepare_playback_media(video_path, wav_path, playback_target)
                if playback_res:
                    meeting.playback_path = str(playback_res)
                    if not meeting.video_source:
                        meeting.video_source = video_path.name

        # MODE B: Single media video - extract audio with FFmpeg
        elif video_path and video_path.exists():
            meeting.processing_step = "Extracting audio with FFmpeg from video..."
            db.commit()

            asr_wav = settings.OUTPUT_DIR / f"meeting_{meeting_id}_audio.wav"
            success, dur, err = extract_and_convert_audio(video_path, asr_wav)
            if success:
                wav_path = asr_wav
                meeting.audio_duration = dur
                meeting.audio_source = "Extracted Video Audio (FFmpeg)"
                duration = max(duration, dur)
            else:
                logger.warning(f"Audio extraction issue: {err}")
                meeting.processing_step = f"FFmpeg warning: {err[:60]}..."

            playback_target = settings.UPLOAD_DIR / f"meeting_{meeting_id}_web_playback.mp4"
            playback_res = prepare_playback_media(video_path, wav_path, playback_target)
            if playback_res:
                meeting.playback_path = str(playback_res)
                if not meeting.video_source:
                    meeting.video_source = video_path.name

        meeting.duration_seconds = round(duration, 2)
        db.commit()

        # 3. Transcribe with faster-whisper
        meeting.processing_step = "Transcribing audio with faster-whisper..."
        db.commit()

        if wav_path and wav_path.exists():
            orig_name = audio_path.name if audio_path else (video_path.name if video_path else meeting.title)
            segments_data = transcribe_audio(
                wav_path,
                language=meeting.language,
                model_size=settings.WHISPER_MODEL_SIZE,
                original_filename=orig_name
            )
        else:
            segments_data = generate_fallback_transcript()

        # Save transcript segments
        db.query(TranscriptSegment).filter(TranscriptSegment.meeting_id == meeting_id).delete()
        saved_segs = []
        for s in segments_data:
            ts_seg = TranscriptSegment(
                meeting_id=meeting_id,
                speaker_label=s["speaker_label"],
                start_time=s["start_time"],
                end_time=s["end_time"],
                text=s["text"],
                confidence=s.get("confidence", 0.95)
            )
            db.add(ts_seg)
            saved_segs.append(ts_seg)
        db.commit()

        # Update duration if was 0
        if duration == 0.0 and saved_segs:
            duration = saved_segs[-1].end_time
            meeting.duration_seconds = duration

        # Populate speakers
        unique_spks = sorted({s["speaker_label"] for s in segments_data})
        existing_spk_labels = {sp.original_label for sp in meeting.speakers}
        for spk_label in unique_spks:
            if spk_label not in existing_spk_labels:
                db.add(Speaker(
                    meeting_id=meeting_id,
                    original_label=spk_label,
                    display_name=spk_label,
                    role="Participant"
                ))
        db.commit()

        # 4. Master NLP Extraction
        meeting.processing_step = "Extracting tasks, decisions, conflicts & dependencies..."
        db.commit()

        # Check for past project decisions for drift detection
        past_decisions = []
        if meeting.project_id:
            past_d_records = db.query(Decision).filter(Decision.project_id == meeting.project_id, Decision.meeting_id != meeting_id).all()
            past_decisions = [d.__dict__ for d in past_d_records]

        participants_list = [sp.display_name for sp in meeting.speakers]
        nlp_results = extract_all_meeting_intelligence(
            segments_data,
            reference_date=meeting.meeting_date,
            past_project_decisions=past_decisions,
            known_participants=participants_list
        )

        # Save Tasks with evidence segment ID
        db.query(Task).filter(Task.meeting_id == meeting_id).delete()
        saved_tasks = []
        for t_data in nlp_results["tasks"]:
            ev_ts = t_data.get("evidence_timestamp")
            seg_match = None
            if ev_ts is not None and saved_segs:
                seg_match = next((s for s in saved_segs if s.start_time <= ev_ts <= s.end_time), None)
                if not seg_match:
                    seg_match = min(saved_segs, key=lambda s: abs(s.start_time - ev_ts))

            task_obj = Task(
                meeting_id=meeting_id,
                project_id=meeting.project_id,
                title=t_data["title"],
                description=t_data["description"],
                owner=t_data["owner"],
                deadline_text=t_data["deadline_text"],
                deadline_normalized=t_data["deadline_normalized"],
                deadline_status=t_data["deadline_status"],
                status=t_data["status"],
                priority=t_data["priority"],
                confidence=t_data["confidence"],
                evidence_quote=t_data["evidence_quote"],
                evidence_timestamp=ev_ts,
                evidence_segment_id=seg_match.id if seg_match else None
            )
            db.add(task_obj)
            saved_tasks.append(task_obj)
        db.commit()

        # Save Decisions
        db.query(Decision).filter(Decision.meeting_id == meeting_id).delete()
        saved_decisions = []
        for d_data in nlp_results["decisions"]:
            dec_obj = Decision(
                meeting_id=meeting_id,
                project_id=meeting.project_id,
                topic=d_data["topic"],
                decision=d_data["decision"],
                status=d_data["status"],
                participants=d_data["participants"],
                evidence_quote=d_data["evidence_quote"],
                evidence_timestamp=d_data["evidence_timestamp"],
                confidence=d_data["confidence"],
                supersedes_previous_decision=d_data.get("supersedes_previous_decision", False),
                previous_decision_id=d_data.get("previous_decision_id"),
                drift_reason=d_data.get("drift_reason")
            )
            db.add(dec_obj)
            saved_decisions.append(dec_obj)
        db.commit()

        # Save Conflicts
        db.query(Conflict).filter(Conflict.meeting_id == meeting_id).delete()
        saved_conflicts = []
        for c_data in nlp_results["conflicts"]:
            conf_obj = Conflict(
                meeting_id=meeting_id,
                topic=c_data["topic"],
                statement_a=c_data["statement_a"],
                speaker_a=c_data.get("speaker_a"),
                timestamp_a=c_data.get("timestamp_a"),
                statement_b=c_data["statement_b"],
                speaker_b=c_data.get("speaker_b"),
                timestamp_b=c_data.get("timestamp_b"),
                status=c_data["status"],
                resolution=c_data.get("resolution")
            )
            db.add(conf_obj)
            saved_conflicts.append(conf_obj)
        db.commit()

        # Save Questions
        db.query(Question).filter(Question.meeting_id == meeting_id).delete()
        for q_data in nlp_results["questions"]:
            db.add(Question(
                meeting_id=meeting_id,
                question=q_data["question"],
                asked_by=q_data.get("asked_by"),
                status=q_data["status"],
                answer=q_data.get("answer"),
                evidence_quote=q_data.get("evidence_quote"),
                evidence_timestamp=q_data.get("evidence_timestamp")
            ))
        db.commit()

        # Save Dependencies
        db.query(Dependency).filter(Dependency.meeting_id == meeting_id).delete()
        saved_dependencies = []
        for dep_data in nlp_results["dependencies"]:
            dep_obj = Dependency(
                meeting_id=meeting_id,
                source_item_type=dep_data["source_item_type"],
                source_label=dep_data["source_label"],
                target_item_type=dep_data["target_item_type"],
                target_label=dep_data["target_label"],
                relation_type=dep_data["relation_type"],
                evidence_quote=dep_data.get("evidence_quote"),
                evidence_timestamp=dep_data.get("evidence_timestamp")
            )
            db.add(dep_obj)
            saved_dependencies.append(dep_obj)
        db.commit()

        # Save Entities
        db.query(Entity).filter(Entity.meeting_id == meeting_id).delete()
        for ent in nlp_results["entities"]:
            db.add(Entity(
                meeting_id=meeting_id,
                text=ent["text"],
                label=ent["label"],
                evidence_timestamp=ent.get("evidence_timestamp")
            ))
        db.commit()

        # 5. Generate MOM
        meeting.processing_step = "Assembling Minutes of Meeting & Workflow..."
        db.commit()

        participants_names = [sp.display_name for sp in meeting.speakers]
        mom_payload = build_mom_document(
            meeting_title=meeting.title,
            meeting_date=meeting.meeting_date,
            duration_seconds=meeting.duration_seconds,
            agenda=meeting.agenda or "Meeting Execution",
            participants=participants_names,
            summary=nlp_results["summary"],
            tasks=[t.__dict__ for t in saved_tasks],
            decisions=[d.__dict__ for d in saved_decisions],
            conflicts=[c.__dict__ for c in saved_conflicts],
            questions=[],
            dependencies=[dep.__dict__ for dep in saved_dependencies]
        )

        meeting.actionability_score = nlp_results["actionability_score"]
        meeting.summary = nlp_results["summary"]
        meeting.mom_json = mom_payload
        meeting.ai_provider = llm_provider.get_active_provider_info()["model_name"]
        meeting.status = "completed"
        meeting.processing_step = "Analysis complete"
        db.commit()
        logger.info(f"Meeting {meeting_id} processed successfully.")

    except Exception as e:
        logger.exception(f"Pipeline error processing meeting {meeting_id}: {e}")
        meeting.status = "error"
        meeting.error_message = str(e)
        meeting.processing_step = f"Error: {str(e)[:120]}"
        db.commit()
