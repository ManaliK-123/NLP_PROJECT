import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import engine, Base, SessionLocal, init_db_migrations
from app.services.meeting_service import seed_demo_data_if_empty
from app.llm.provider import llm_provider

# Import routers
from app.api.meetings import router as meetings_router
from app.api.tasks import router as tasks_router
from app.api.decisions import router as decisions_router
from app.api.projects import router as projects_router
from app.api.analytics import router as analytics_router
from app.api.evaluation import router as evaluation_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables, apply column migrations and seed demo data
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    init_db_migrations()
    
    db = SessionLocal()
    try:
        seed_demo_data_if_empty(db)
    finally:
        db.close()
        
    logger.info(f"System ready! Active AI Provider: {llm_provider.get_active_provider_info()['model_name']}")
    yield
    # Shutdown
    logger.info("Application shutdown.")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="NLP-Based Intelligent Meeting Analysis and Execution System",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount media uploads directory and testdata
app.mount("/media_files", StaticFiles(directory=str(settings.UPLOAD_DIR)), name="media_files")
app.mount("/testdata", StaticFiles(directory=str(settings.TESTDATA_DIR)), name="testdata")

# Include API routers
app.include_router(meetings_router)
app.include_router(tasks_router)
app.include_router(decisions_router)
app.include_router(projects_router)
app.include_router(analytics_router)
app.include_router(evaluation_router)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "provider": llm_provider.get_active_provider_info()
    }

@app.get("/")
def root():
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "tagline": "Turn every conversation into action.",
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
