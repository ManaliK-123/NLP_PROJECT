from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db_migrations():
    """Ensure newly added columns exist in the SQLite database without requiring a reset."""
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            cursor = conn.execute(text("PRAGMA table_info(meetings)"))
            existing_cols = {row[1] for row in cursor.fetchall()}
            cols_to_add = [
                ("video_path", "VARCHAR(512)"),
                ("playback_path", "VARCHAR(512)"),
                ("audio_source", "VARCHAR(100) DEFAULT 'extracted_video_audio'"),
                ("video_source", "VARCHAR(255)"),
                ("external_audio_name", "VARCHAR(255)"),
                ("video_duration", "FLOAT DEFAULT 0.0"),
                ("audio_duration", "FLOAT DEFAULT 0.0"),
                ("media_validation_status", "VARCHAR(50) DEFAULT 'valid'"),
                ("media_validation_message", "TEXT")
            ]
            for col_name, col_def in cols_to_add:
                if col_name not in existing_cols:
                    conn.execute(text(f"ALTER TABLE meetings ADD COLUMN {col_name} {col_def}"))
            conn.commit()
        except Exception:
            pass
