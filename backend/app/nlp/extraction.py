import re
import datetime
from typing import List, Dict, Any, Optional

from app.nlp.task_detector import detect_tasks
from app.nlp.decision_detector import detect_decisions
from app.nlp.conflict_detector import detect_conflicts
from app.nlp.dependency_detector import detect_dependencies
from app.nlp.ambiguity_detector import analyze_ambiguity

QUESTION_PATTERNS = [
    r"\?$",
    r"^(?:Can|Could|Would|Should|Is|Are|Who|What|Why|How|Where|When)\b"
]

def extract_questions(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Detect questions and determine if they were resolved or remain open."""
    questions = []
    
    for i, seg in enumerate(segments):
        text = seg["text"].strip()
        is_q = text.endswith("?") or any(re.search(pat, text, re.IGNORECASE) for pat in QUESTION_PATTERNS)
        
        # Also treat "We haven't decided..." as an open question/issue if not already captured
        if is_q:
            # Check if next segment provides an immediate answer
            has_answer = False
            answer_text = None
            if i + 1 < len(segments):
                next_text = segments[i + 1]["text"]
                if not next_text.endswith("?") and not any(re.search(pat, next_text, re.IGNORECASE) for pat in QUESTION_PATTERNS):
                    has_answer = True
                    answer_text = next_text
                    
            questions.append({
                "question": text,
                "asked_by": seg.get("speaker_label", "Participant"),
                "status": "Answered" if has_answer else "Unresolved",
                "answer": answer_text,
                "evidence_quote": text,
                "evidence_timestamp": seg["start_time"]
            })
            
    return questions

def extract_entities(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract Named Entities (PERSON, DATE, TECH, MILESTONE) from transcript."""
    entities = []
    known_names = {"Rahul", "Priya", "Alex", "Sam", "Professor"}
    known_tech = {"PyTorch", "TensorFlow", "Whisper", "BERT", "Vite", "React", "FastAPI", "SQLite"}
    days_and_dates = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Tomorrow", "Today"}
    
    seen = set()
    for seg in segments:
        words = seg["text"].split()
        for w in words:
            clean = re.sub(r"[^\w]", "", w)
            if not clean:
                continue
                
            key = (clean, seg["start_time"])
            if key in seen:
                continue
                
            if clean in known_names:
                entities.append({
                    "text": clean,
                    "label": "PERSON",
                    "evidence_timestamp": seg["start_time"]
                })
                seen.add(key)
            elif clean in known_tech:
                entities.append({
                    "text": clean,
                    "label": "TECH",
                    "evidence_timestamp": seg["start_time"]
                })
                seen.add(key)
            elif clean in days_and_dates:
                entities.append({
                    "text": clean,
                    "label": "DATE",
                    "evidence_timestamp": seg["start_time"]
                })
                seen.add(key)
                
    return entities

def compute_actionability_score(tasks: List[Dict[str, Any]], decisions: List[Dict[str, Any]], conflicts: List[Dict[str, Any]]) -> float:
    """
    Calculate 0.0 - 100.0 score of how actionable and well-defined the meeting outcome is.
    Penalizes conflicts, unassigned tasks, and unresolved decisions.
    """
    if not tasks and not decisions:
        return 50.0
        
    score = 70.0
    
    # +10 for each confirmed task with owner and deadline
    for t in tasks:
        if t.get("owner") != "Unassigned":
            score += 5.0
        else:
            score -= 5.0
            
        if t.get("deadline_status") == "Exact":
            score += 5.0
        elif t.get("deadline_status") == "Not specified":
            score -= 3.0
            
    # Decisions
    for d in decisions:
        if d.get("status") == "Final":
            score += 5.0
        elif d.get("status") == "Undecided":
            score -= 4.0
            
    # Conflicts penalize execution readiness
    score -= len(conflicts) * 10.0
    
    return max(10.0, min(100.0, round(score, 1)))

def generate_meeting_summary(
    segments: List[Dict[str, Any]],
    tasks: List[Dict[str, Any]],
    decisions: List[Dict[str, Any]],
    conflicts: List[Dict[str, Any]]
) -> str:
    """Generate professional executive summary of the meeting."""
    points = []
    points.append(f"Meeting convened with {len(segments)} discussion turns recorded.")
    
    if tasks:
        assigned = [t for t in tasks if t['owner'] != 'Unassigned']
        points.append(f"Detected {len(tasks)} action items ({len(assigned)} assigned to owners including {', '.join({t['owner'] for t in assigned})}).")
        
    if decisions:
        final_d = [d for d in decisions if d['status'] == 'Final']
        undecided_d = [d for d in decisions if d['status'] == 'Undecided']
        if final_d:
            points.append(f"Key finalized decisions: {', '.join([d['decision'] for d in final_d])}.")
        if undecided_d:
            points.append(f"Unresolved matters pending confirmation: {', '.join([d['decision'] for d in undecided_d])}.")
            
    if conflicts:
        points.append(f"Identified {len(conflicts)} scheduling/factual conflict requiring immediate clarification: {conflicts[0]['topic']}.")
        
    return " ".join(points)

def extract_all_meeting_intelligence(
    segments: List[Dict[str, Any]],
    reference_date: Optional[datetime.datetime] = None,
    past_project_decisions: Optional[List[Dict[str, Any]]] = None,
    known_participants: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Main pipeline entry point: Runs all NLP extraction services.
    """
    # 1. Tasks
    raw_tasks = detect_tasks(segments, reference_date, known_participants)
    tasks = analyze_ambiguity(raw_tasks)
    
    # 2. Decisions & Drift
    decisions = detect_decisions(segments, past_project_decisions)
    
    # 3. Conflicts
    conflicts = detect_conflicts(segments)
    
    # 4. Questions
    questions = extract_questions(segments)
    
    # 5. Dependencies
    dependencies = detect_dependencies(segments, tasks)
    for dep in dependencies:
        if dep.get("relation_type") == "blocks":
            target_label = dep.get("target_label", "").lower()
            for t in tasks:
                if t["title"].lower() in target_label or target_label in t["title"].lower():
                    if t.get("status") in ("Pending", "In Progress", "Needs Clarification"):
                        t["status"] = "Blocked"
    
    # 6. Entities
    entities = extract_entities(segments)
    
    # 7. Actionability score
    actionability_score = compute_actionability_score(tasks, decisions, conflicts)
    
    # 8. Summary
    summary = generate_meeting_summary(segments, tasks, decisions, conflicts)
    
    return {
        "tasks": tasks,
        "decisions": decisions,
        "conflicts": conflicts,
        "questions": questions,
        "dependencies": dependencies,
        "entities": entities,
        "actionability_score": actionability_score,
        "summary": summary
    }
