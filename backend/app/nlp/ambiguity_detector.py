import re
from typing import List, Dict, Any

VAGUE_OWNER_PATTERNS = [
    r"\b(?:someone|somebody|anybody|anyone|team|we should have someone|needs to be handled|must be taken care of)\b"
]

VAGUE_DEADLINE_PATTERNS = [
    r"\b(?:soon|later|eventually|in the future|sometime|asap|when possible|when you get a chance)\b"
]

def analyze_ambiguity(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Annotate tasks with explicit ambiguity diagnostics.
    """
    enriched_tasks = []
    
    for t in tasks:
        task_copy = dict(t)
        ambiguities = []
        
        # Check owner ambiguity
        if task_copy.get("owner") in ("Unassigned", "Unknown", None) or task_copy.get("status") == "Needs Clarification":
            ambiguities.append({
                "type": "Unassigned Owner",
                "message": "Task does not have a confirmed individual owner.",
                "remedy": "Assign explicit owner during review."
            })
            task_copy["owner"] = "Unassigned"
            task_copy["status"] = "Needs Clarification"

        # Check deadline ambiguity
        dl_status = task_copy.get("deadline_status")
        if dl_status in ("Ambiguous", "Not specified") or not task_copy.get("deadline_text"):
            ambiguities.append({
                "type": "Vague Deadline",
                "message": f"Deadline is {dl_status.lower() if dl_status else 'missing'}.",
                "remedy": "Specify a calendar date or explicit milestone."
            })
            if not task_copy.get("deadline_status"):
                task_copy["deadline_status"] = "Not specified"

        task_copy["ambiguities"] = ambiguities
        enriched_tasks.append(task_copy)
        
    return enriched_tasks
