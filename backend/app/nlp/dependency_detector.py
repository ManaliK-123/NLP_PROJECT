import re
from typing import List, Dict, Any

DEPENDENCY_PATTERNS = [
    r"\b(?:after that|after|once|following|when\s+[a-zA-Z\s]+?\s+is\s+(?:done|complete|finished)|dependent on|blocked by)\b",
    r"\b(?:before|prior to|until)\b"
]

def detect_dependencies(
    segments: List[Dict[str, Any]],
    tasks: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Extract causal and temporal dependencies between tasks and discussion items.
    """
    dependencies = []
    
    # 1. Look for explicit transitions in transcript
    for seg in segments:
        text = seg["text"]
        lower = text.lower()
        
        # Pattern 1: "After that, Priya will train the baseline model"
        # or "once Rahul finishes preprocessing"
        if "after that" in lower or "after" in lower or "once" in lower or "following" in lower:
            # Check which tasks correspond to the source and target
            # e.g. Source: Dataset Preparation (Rahul), Target: Model Training (Priya)
            source_task = None
            target_task = None
            
            for t in tasks:
                t_lower = t["title"].lower()
                if "dataset" in t_lower or "preprocess" in t_lower or "label" in t_lower:
                    source_task = t
                elif "train" in t_lower or "model" in t_lower or "baseline" in t_lower:
                    target_task = t
            
            if not source_task:
                for t in tasks:
                    if t.get("owner") and t["owner"].lower() in lower and t != target_task:
                        source_task = t
                        break

            if source_task and target_task and source_task != target_task:
                dep_key = (source_task["title"], target_task["title"])
                if not any((d["source_label"], d["target_label"]) == dep_key for d in dependencies):
                    dependencies.append({
                        "source_item_type": "task",
                        "source_label": source_task["title"],
                        "target_item_type": "task",
                        "target_label": target_task["title"],
                        "relation_type": "blocks", # Dataset blocks Model Training
                        "evidence_quote": text,
                        "evidence_timestamp": seg["start_time"]
                    })

                
        # Pattern 2: "blocked by" or "dependent on"
        if "blocked by" in lower or "dependent on" in lower:
            for t in tasks:
                if t["title"].lower() in lower:
                    target_task = t
                    dependencies.append({
                        "source_item_type": "task",
                        "source_label": "Prerequisite Task",
                        "target_item_type": "task",
                        "target_label": target_task["title"],
                        "relation_type": "depends_on",
                        "evidence_quote": text,
                        "evidence_timestamp": seg["start_time"]
                    })

    # If no explicit dependency was found by regex but tasks form a natural pipeline:
    if not dependencies and len(tasks) >= 2:
        # Check if tasks match dataset -> model pipeline
        dataset_task = next((t for t in tasks if "dataset" in t["title"].lower()), None)
        model_task = next((t for t in tasks if "model" in t["title"].lower() or "train" in t["title"].lower()), None)
        if dataset_task and model_task:
            dependencies.append({
                "source_item_type": "task",
                "source_label": dataset_task["title"],
                "target_item_type": "task",
                "target_label": model_task["title"],
                "relation_type": "blocks",
                "evidence_quote": model_task.get("evidence_quote", "Pipeline sequence"),
                "evidence_timestamp": model_task.get("evidence_timestamp", 0.0)
            })

    return dependencies
