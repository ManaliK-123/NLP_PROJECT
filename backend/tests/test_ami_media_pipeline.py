import os
import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.models import Meeting, Task, Decision, TranscriptSegment
from app.media.processor import inspect_media, validate_media_pair
from app.services.meeting_service import process_meeting_pipeline

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

def test_media_inspection_and_stream_detection():
    corner_avi = Path(r"d:\NLP_PROJECT\testdata\ES2002a.Corner.avi")
    headset_wav = Path(r"d:\NLP_PROJECT\testdata\ES2002a.Mix-Headset.wav")
    demo_mp4 = Path(r"d:\NLP_PROJECT\testdata\ES2002a_meeting_demo.mp4")

    # Corner AVI has video, NO audio
    if corner_avi.exists():
        info_avi = inspect_media(corner_avi)
        assert info_avi["valid"] is True
        assert info_avi["has_video"] is True
        assert info_avi["has_audio"] is False
        assert info_avi["duration"] > 1200 # ~20m 48s

    # Headset WAV has audio, NO video
    if headset_wav.exists():
        info_wav = inspect_media(headset_wav)
        assert info_wav["valid"] is True
        assert info_wav["has_video"] is False
        assert info_wav["has_audio"] is True
        assert info_wav["duration"] > 1200 # ~21m 12s

    # Demo MP4 has both video and audio
    if demo_mp4.exists():
        info_mp4 = inspect_media(demo_mp4)
        assert info_mp4["valid"] is True
        assert info_mp4["has_video"] is True
        assert info_mp4["has_audio"] is True

def test_mode_a_paired_media_validation():
    corner_avi = Path(r"d:\NLP_PROJECT\testdata\ES2002a.Corner.avi")
    headset_wav = Path(r"d:\NLP_PROJECT\testdata\ES2002a.Mix-Headset.wav")

    if corner_avi.exists() and headset_wav.exists():
        res = validate_media_pair(corner_avi, headset_wav)
        assert res["valid"] is True
        assert res["mode"] == "paired"
        assert res["video_detected"] is True
        assert res["audio_detected"] is True
        # Flags duration discrepancy notice without failing
        assert "duration discrepancy" in res["message"].lower() or res["status"] in ["valid", "warning"]

def test_mode_b_single_media_validation():
    demo_mp4 = Path(r"d:\NLP_PROJECT\testdata\ES2002a_meeting_demo.mp4")
    if demo_mp4.exists():
        res = validate_media_pair(demo_mp4, None)
        assert res["valid"] is True
        assert res["mode"] == "single"
        assert res["video_detected"] is True
        assert res["audio_detected"] is True

def test_mode_a_paired_pipeline_execution(db):
    corner_avi = Path(r"d:\NLP_PROJECT\testdata\ES2002a.Corner.avi")
    headset_wav = Path(r"d:\NLP_PROJECT\testdata\ES2002a.Mix-Headset.wav")

    if not corner_avi.exists() or not headset_wav.exists():
        pytest.skip("Test media not present")

    meeting = Meeting(
        title="AMI ES2002a Paired Test Case",
        video_path=str(corner_avi),
        audio_path=str(headset_wav),
        media_path=str(corner_avi),
        media_type="video",
        audio_source="External Headset Audio (WAV)",
        status="pending"
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    # Process meeting through pipeline
    process_meeting_pipeline(db, meeting.id)
    db.refresh(meeting)

    assert meeting.status == "completed"
    assert meeting.media_validation_status in ["valid", "warning"]
    assert "External Headset Audio" in (meeting.audio_source or "")
    assert len(meeting.segments) > 0
    assert len(meeting.speakers) >= 2
    assert meeting.duration_seconds > 1000
    assert meeting.mom_json is not None
