import re
import datetime
from typing import List, Dict, Any, Optional
from app.nlp.deadline_detector import detect_deadline

# Linguistic markers
TASK_INDICATORS = [
    r"\b(?:will|shall|must|needs? to|has to|have to|assigned to|responsible for|take care of|handle|going to|action item)\b",
    r"\b(?:please|make sure to|ensure that|prepare|implement|develop|train|build|create|write|push|deploy|finalize|complete)\b"
]

COMPLETED_INDICATORS = [
    r"\b(?:already|finished|completed|done|has updated|updated|has created|created|trained the|fixed the|implemented)\b"
]

SUGGESTION_INDICATORS = [
    r"\b(?:maybe|perhaps|could|might|suggest|recommend|how about|we could|what if)\b"
]

QUESTION_INDICATORS = [
    r"\?$",
    r"^(?:can|could|would|will|should|is|are|who|what|why|how)\b"
]

UNASSIGNED_INDICATORS = [
    r"\b(?:someone|anybody|anyone|team|we need someone|somebody|it should be done|needs to be handled)\b"
]

PRIORITY_CRITICAL_WORDS = {"urgent", "critical", "immediately", "blocker", "asap", "emergency"}
PRIORITY_HIGH_WORDS = {"high priority", "important", "crucial", "by tomorrow", "must have"}
PRIORITY_LOW_WORDS = {"nice to have", "low priority", "if time permits", "later"}

def classify_utterance_type(text: str) -> str:
    """
    Classify whether an utterance is:
    'task', 'completed', 'suggestion', 'question', or 'discussion'
    """
    clean_text = text.strip().lower()
    
    # Check question
    if clean_text.endswith("?") or any(re.search(pat, clean_text) for pat in QUESTION_INDICATORS):
        return "question"
        
    # Check suggestion (e.g. "Maybe Rahul can update the report")
    if any(re.search(pat, clean_text) for pat in SUGGESTION_INDICATORS):
        return "suggestion"
        
    # Check completed work (e.g. "Rahul updated the report")
    if any(re.search(pat, clean_text) for pat in COMPLETED_INDICATORS) and not any(re.search(r"\b(?:will|by|tomorrow|later)\b", clean_text) for _ in [1]):
        return "completed"
        
    # Check task assignment
    if any(re.search(pat, clean_text) for pat in TASK_INDICATORS):
        return "task"
        
    return "discussion"

EXCLUDED_VOCATIVE_WORDS = {
    "well", "okay", "ok", "yeah", "yes", "no", "sure", "actually", "alright", "wait", "so", "now",
    "after", "before", "complete", "please", "make", "ensure", "first", "then", "let", "lets", "someone",
    "anybody", "good", "update", "train", "check", "review", "here", "there", "also", "next", "we", "i",
    "the", "this", "that", "since", "once", "while"
}

class Tuple_Owner:
    def __init__(self, name: str, is_unassigned: bool):
        self.name = name
        self.is_unassigned = is_unassigned

def extract_owner(text: str, speaker_label: str, known_participants: Optional[List[str]] = None) -> Tuple_Owner:
    """
    Extract task owner.
    Returns: (owner_name, is_unassigned)
    """
    clean_text = text.strip()
    
    # 1. Check for unassigned markers
    if any(re.search(pat, clean_text, re.IGNORECASE) for pat in UNASSIGNED_INDICATORS):
        return Tuple_Owner("Unassigned", True)

    # 2. Check first-person commitment: "I will...", "I'll handle..."
    if re.search(r"\b(?:i will|i'll|i can|i am going to|i'm going to|i'm taking|i'll take care of|i shall)\b", clean_text, re.IGNORECASE):
        if speaker_label and not re.match(r"^Speaker\s*\d*$", speaker_label, re.IGNORECASE):
            return Tuple_Owner(speaker_label, False)
        elif known_participants:
            for p in known_participants:
                if p.lower() in clean_text.lower():
                    return Tuple_Owner(p, False)
        return Tuple_Owner(speaker_label or "Unassigned", False if speaker_label else True)

    # 3. Check vocative with punctuation: "Rahul, complete the dataset..." or "...sync. Rahul, complete..."
    vocative_punct = re.search(r"(?:^|[.!?]\s+)([A-Z][a-zA-Z]+)\s*[,:]\s+", clean_text)
    if not vocative_punct:
        # Also check without sentence boundary if followed by task verb
        vocative_punct = re.search(r"\b([A-Z][a-zA-Z]+)\s*,\s+(?:please\s+|make sure to\s+|complete|train|update|implement|lead|handle|review|send|prepare)\b", clean_text, re.IGNORECASE)
    if vocative_punct:
        name = vocative_punct.group(1)
        if name.lower() not in EXCLUDED_VOCATIVE_WORDS:
            return Tuple_Owner(name, False)


    # 4. Check known participants in vocative / start position
    if known_participants:
        for p in known_participants:
            if re.match(rf"^{re.escape(p)}\b", clean_text, re.IGNORECASE):
                return Tuple_Owner(p, False)

    # 5. Check for pattern: "Priya will train...", "Rahul to handle..."
    action_match = re.search(r"\b([A-Z][a-zA-Z]+)\s+(?:will|is going to|to handle|to lead|shall|takes care of)\b", clean_text)
    if action_match:
        name = action_match.group(1)
        if name.lower() not in EXCLUDED_VOCATIVE_WORDS:
            return Tuple_Owner(name, False)

    # 6. Check against known participant list anywhere in utterance
    if known_participants:
        for p in known_participants:
            if re.search(rf"\b{re.escape(p)}\b", clean_text, re.IGNORECASE):
                return Tuple_Owner(p, False)

    # 7. If the speaker is a named person (not generic "Speaker 1") and making a direct imperative/task
    if speaker_label and not re.match(r"^Speaker\s*\d*$", speaker_label, re.IGNORECASE) and speaker_label not in ("Unknown", "Team"):
        return Tuple_Owner(speaker_label, False)

    # Default: Unassigned
    return Tuple_Owner("Unassigned", True)


def detect_tasks(
    segments: List[Dict[str, Any]],
    reference_date: Optional[datetime.datetime] = None,
    known_participants: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Detect actionable tasks from transcript segments with full evidence tracing.
    """
    tasks = []
    
    for seg in segments:
        text = seg["text"].strip()
        utt_type = classify_utterance_type(text)
        
        # We only create Task objects for actual confirmed tasks, or passive tasks that need clarification
        is_passive_unassigned = any(re.search(pat, text, re.IGNORECASE) for pat in UNASSIGNED_INDICATORS)
        
        if utt_type != "task" and not is_passive_unassigned:
            continue
            
        owner_info = extract_owner(text, seg.get("speaker_label", "Speaker"), known_participants)
        owner = owner_info.name
        
        # Determine status
        status = "Needs Clarification" if owner_info.is_unassigned else "Pending"
        
        # Extract deadline
        dl_info = detect_deadline(text, reference_date)
        
        # Priority
        lower = text.lower()
        if any(w in lower for w in PRIORITY_CRITICAL_WORDS):
            priority = "Critical"
        elif any(w in lower for w in PRIORITY_HIGH_WORDS):
            priority = "High"
        elif any(w in lower for w in PRIORITY_LOW_WORDS):
            priority = "Low"
        else:
            priority = "Medium"
            
        # Clean task title
        title = clean_task_title(text, owner)
        
        confidence = seg.get("confidence", 0.95)
        if owner_info.is_unassigned:
            confidence = max(0.65, confidence * 0.85)
            
        tasks.append({
            "title": title,
            "description": f"Extracted commitment: \"{text}\"",
            "owner": owner,
            "deadline_text": dl_info["deadline_text"],
            "deadline_normalized": dl_info["deadline_normalized"],
            "deadline_status": dl_info["deadline_status"],
            "status": status,
            "priority": priority,
            "confidence": round(confidence, 2),
            "evidence_quote": text,
            "evidence_timestamp": seg["start_time"],
            "evidence_segment_id": seg.get("id")
        })
        
    return tasks

def clean_task_title(text: str, owner: str) -> str:
    """Generate concise, actionable task title."""
    cleaned = text
    # Remove discourse markers and introductory meeting phrases
    cleaned = re.sub(r"^(?:Alright team,?\s*|Okay team,?\s*|Let's start the sync[.,]?\s*|Sure,?\s*|Yes,?\s*|So,?\s*|Good catch!?,?\s*)+", "", cleaned, flags=re.IGNORECASE)
    # Remove leading vocatives: "Rahul, " or "Rahul: "
    cleaned = re.sub(rf"^(?:[A-Z][a-zA-Z]+\s*[,:]\s*|{re.escape(owner)}\s*[,:]\s*)", "", cleaned, flags=re.IGNORECASE)
    # Remove leading temporal/subordinate clauses like "After Rahul finishes it, " or "Once Rahul finishes preprocessing, "
    cleaned = re.sub(r"^(?:after\s+[a-zA-Z\s]+?(?:finishes|done|complete|pushes)[a-zA-Z\s]*,\s*)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(?:once\s+[a-zA-Z\s]+?(?:finishes|done|complete)[a-zA-Z\s]*,\s*)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(?:please|make sure to|ensure that|i will|i'll|i will take care of|someone should)\s+", "", cleaned, flags=re.IGNORECASE)

    cleaned = cleaned.strip()
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned[:100] if len(cleaned) > 100 else cleaned

