from fastapi import APIRouter
from app.nlp.evaluation import run_nlp_benchmark

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])

@router.get("/benchmark")
def get_evaluation_benchmark():
    """Return academic NLP benchmark metrics comparing Rule-Based, Transformer, and Hybrid approaches."""
    return run_nlp_benchmark()
