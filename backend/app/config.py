import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
DATA_DIR = BASE_DIR / "data"

for directory in [UPLOAD_DIR, OUTPUT_DIR, DATA_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    APP_NAME: str = "MEETING → EXECUTION"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'meeting_execution.db'}"
    
    # LLM Settings (Optional - fallback to Local Rule/Heuristic Engine)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto") # auto, gemini, ollama, local
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")
    
    # Whisper settings
    WHISPER_MODEL_SIZE: str = os.getenv("WHISPER_MODEL_SIZE", "tiny") # tiny, base, small
    WHISPER_COMPUTE_TYPE: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    
    # Paths
    BASE_DIR: Path = BASE_DIR
    UPLOAD_DIR: Path = UPLOAD_DIR
    OUTPUT_DIR: Path = OUTPUT_DIR
    DATA_DIR: Path = DATA_DIR
    TESTDATA_DIR: Path = BASE_DIR / "testdata"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
