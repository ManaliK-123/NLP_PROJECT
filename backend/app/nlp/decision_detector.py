import re
from typing import List, Dict, Any, Optional

FINAL_DECISION_PATTERNS = [
    r"\b(?:agreed|decided|finalized|settled on|confirmed that|we will proceed with|the decision is|consensus is)\b",
    r"\b(?:okay,?\s*(?:we will|let's)|all right,?\s*we'll go with)\b"
]

UNDECIDED_PATTERNS = [
    r"\b(?:haven't decided|not decided|yet to decide|undecided|open question|need to discuss|up in the air|still considering)\b",
    r"\b(?:discuss that in|talk about that later|tbd|to be decided)\b"
]

TENTATIVE_PATTERNS = [
    r"\b(?:for now|tentatively|provisionally|leaning towards|let's assume|temporary decision)\b"
]

REJECTED_PATTERNS = [
    r"\b(?:decided against|ruled out|won't use|not going to use|rejected the idea)\b"
]

def detect_decisions(
    segments: List[Dict[str, Any]],
    past_project_decisions: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """
    Detect decisions (Final, Tentative, Undecided, Rejected) and check for Decision Drift.
    """
    decisions = []
    
    for seg in segments:
        text = seg["text"].strip()
        lower = text.lower()
        
        # Check undecided first (e.g. "We haven't decided which architecture to use")
        if any(re.search(pat, lower) for pat in UNDECIDED_PATTERNS):
            topic = extract_topic(text)
            decisions.append({
                "topic": topic,
                "decision": text,
                "status": "Undecided",
                "participants": seg.get("speaker_label", "Team"),
                "evidence_quote": text,
                "evidence_timestamp": seg["start_time"],
                "confidence": 0.94,
                "supersedes_previous_decision": False,
                "previous_decision_id": None,
                "drift_reason": None
            })
            continue

        # Check rejected
        if any(re.search(pat, lower) for pat in REJECTED_PATTERNS):
            topic = extract_topic(text)
            decisions.append({
                "topic": topic,
                "decision": text,
                "status": "Rejected",
                "participants": seg.get("speaker_label", "Team"),
                "evidence_quote": text,
                "evidence_timestamp": seg["start_time"],
                "confidence": 0.92,
                "supersedes_previous_decision": False,
                "previous_decision_id": None,
                "drift_reason": None
            })
            continue

        # Check tentative
        if any(re.search(pat, lower) for pat in TENTATIVE_PATTERNS):
            topic = extract_topic(text)
            decisions.append({
                "topic": topic,
                "decision": text,
                "status": "Tentative",
                "participants": seg.get("speaker_label", "Team"),
                "evidence_quote": text,
                "evidence_timestamp": seg["start_time"],
                "confidence": 0.88,
                "supersedes_previous_decision": False,
                "previous_decision_id": None,
                "drift_reason": None
            })
            continue

        # Check final decision
        if any(re.search(pat, lower) for pat in FINAL_DECISION_PATTERNS):
            topic = extract_topic(text)
            
            # Check for Decision Drift against past decisions in the project
            drift_detected = False
            prev_id = None
            drift_reason = None
            
            if past_project_decisions:
                for past_d in past_project_decisions:
                    # If topics overlap and new decision text differs
                    if past_d.get("topic") and past_d["topic"].lower() in topic.lower():
                        drift_detected = True
                        prev_id = past_d.get("id")
                        drift_reason = f"Decision drifted from '{past_d.get('decision')}' in meeting #{past_d.get('meeting_id')} to '{text}'."
                        break
                        
            decisions.append({
                "topic": topic,
                "decision": text,
                "status": "Final",
                "participants": seg.get("speaker_label", "Team"),
                "evidence_quote": text,
                "evidence_timestamp": seg["start_time"],
                "confidence": 0.95,
                "supersedes_previous_decision": drift_detected,
                "previous_decision_id": prev_id,
                "drift_reason": drift_reason
            })

    return decisions

def extract_topic(text: str) -> str:
    """Extract a concise topic label from decision utterance."""
    lower = text.lower()
    if "architecture" in lower:
        return "Model Architecture"
    if "dataset" in lower:
        return "Dataset Selection"
    if "report" in lower or "submission" in lower:
        return "Report Submission"
    if "framework" in lower or "pytorch" in lower or "tensorflow" in lower:
        return "Framework & Tech Stack"
    if "evaluation" in lower or "metric" in lower:
        return "Evaluation Strategy"
    
    # Generic cleanup
    clean = re.sub(r"^(?:We haven't decided|We agreed to|We decided to|Okay, we will)\s+", "", text, flags=re.IGNORECASE)
    return clean[:45] + ("..." if len(clean) > 45 else "")
