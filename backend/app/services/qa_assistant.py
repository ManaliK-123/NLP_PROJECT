import re
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models.models import Meeting, Task, Decision, Conflict, TranscriptSegment

def ask_meeting_assistant(db: Session, meeting_id: int, user_question: str) -> Dict[str, Any]:
    """
    Answers queries strictly grounded in meeting transcript segments and extracted execution objects.
    Returns answer + verifiable evidence items with timestamps.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        return {"answer": "Meeting not found.", "evidence": [], "grounded_in": []}

    q_lower = user_question.lower()
    evidence_items = []
    grounded_in = []
    
    # 1. Query: Unresolved items / open questions
    if "unresolved" in q_lower or "open" in q_lower or "pending" in q_lower or "not decided" in q_lower:
        undecided_decisions = db.query(Decision).filter(Decision.meeting_id == meeting_id, Decision.status.in_(["Undecided", "Tentative"])).all()
        clarification_tasks = db.query(Task).filter(Task.meeting_id == meeting_id, Task.status.in_(["Needs Clarification", "Blocked"])).all()
        conflicts = db.query(Conflict).filter(Conflict.meeting_id == meeting_id).all()
        
        parts = []
        if undecided_decisions:
            for d in undecided_decisions:
                parts.append(f"Decision required: '{d.decision}'")
                evidence_items.append({
                    "timestamp": d.evidence_timestamp or 0.0,
                    "speaker": d.participants or "Team",
                    "quote": d.evidence_quote or d.decision
                })
            grounded_in.append("decisions")
            
        if clarification_tasks:
            for t in clarification_tasks:
                parts.append(f"Task '{t.title}' needs explicit owner assignment (currently {t.owner}).")
                evidence_items.append({
                    "timestamp": t.evidence_timestamp or 0.0,
                    "speaker": "Transcript",
                    "quote": t.evidence_quote or t.title
                })
            grounded_in.append("tasks")
            
        if conflicts:
            for c in conflicts:
                parts.append(f"Scheduling conflict: '{c.topic}' ({c.statement_a} vs {c.statement_b}).")
                evidence_items.append({
                    "timestamp": c.timestamp_b or 0.0,
                    "speaker": c.speaker_b or "Speaker",
                    "quote": c.statement_b
                })
            grounded_in.append("conflicts")
            
        answer = "Here are the unresolved items identified in this meeting:\n" + "\n".join(f"• {p}" for p in parts)
        return {"answer": answer, "evidence": evidence_items, "grounded_in": grounded_in}

    # 2. Query: Who owns / who is responsible
    if "who owns" in q_lower or "who is responsible" in q_lower or "owner" in q_lower or "assigned" in q_lower:
        tasks = db.query(Task).filter(Task.meeting_id == meeting_id).all()
        matched_tasks = []
        for t in tasks:
            # Check if keyword in task title or description
            words = [w for w in q_lower.replace("?", "").split() if w not in {"who", "owns", "is", "responsible", "for", "the", "task"}]
            if any(w in t.title.lower() or (t.description and w in t.description.lower()) for w in words):
                matched_tasks.append(t)
                
        if not matched_tasks and tasks:
            matched_tasks = tasks # return all task assignments
            
        answers = []
        for t in matched_tasks:
            answers.append(f"'{t.title}' is assigned to {t.owner} (Deadline: {t.deadline_text or 'Not specified'}).")
            evidence_items.append({
                "timestamp": t.evidence_timestamp or 0.0,
                "speaker": "Transcript",
                "quote": t.evidence_quote or t.title
            })
            
        grounded_in.append("tasks")
        return {
            "answer": "Owner assignments:\n" + "\n".join(f"• {a}" for a in answers),
            "evidence": evidence_items,
            "grounded_in": grounded_in
        }

    # 3. Query: Deadlines / schedule / due
    if "deadline" in q_lower or "due" in q_lower or "schedule" in q_lower or "date" in q_lower:
        tasks = db.query(Task).filter(Task.meeting_id == meeting_id).all()
        conflicts = db.query(Conflict).filter(Conflict.meeting_id == meeting_id).all()
        answers = []
        for t in tasks:
            if t.deadline_text:
                answers.append(f"Task '{t.title}': {t.deadline_text} (Owner: {t.owner}).")
                evidence_items.append({
                    "timestamp": t.evidence_timestamp or 0.0,
                    "speaker": "Transcript",
                    "quote": t.evidence_quote or t.title
                })
        for c in conflicts:
            answers.append(f"Notice: Conflict detected for {c.topic}: '{c.statement_a}' vs '{c.statement_b}'.")
            evidence_items.append({
                "timestamp": c.timestamp_b or 0.0,
                "speaker": c.speaker_b or "Speaker",
                "quote": c.statement_b
            })
        grounded_in.extend(["tasks", "conflicts"])
        return {
            "answer": "Deadlines discussed in this meeting:\n" + "\n".join(f"• {a}" for a in answers),
            "evidence": evidence_items,
            "grounded_in": grounded_in
        }

    # 4. Query: Why At Risk / execution health
    if "why" in q_lower and ("risk" in q_lower or "health" in q_lower or "status" in q_lower):
        from app.services.execution_radar import calculate_execution_radar
        tasks_list = [t.__dict__ for t in db.query(Task).filter(Task.meeting_id == meeting_id).all()]
        dec_list = [d.__dict__ for d in db.query(Decision).filter(Decision.meeting_id == meeting_id).all()]
        conf_list = [c.__dict__ for c in db.query(Conflict).filter(Conflict.meeting_id == meeting_id).all()]
        radar = calculate_execution_radar(tasks_list, dec_list, conf_list, [])
        
        reasons = radar["reasons"]
        for c in db.query(Conflict).filter(Conflict.meeting_id == meeting_id).all():
            evidence_items.append({
                "timestamp": c.timestamp_b or 0.0,
                "speaker": c.speaker_b or "Speaker",
                "quote": c.statement_b
            })
        for d in db.query(Decision).filter(Decision.meeting_id == meeting_id, Decision.status == "Undecided").all():
            evidence_items.append({
                "timestamp": d.evidence_timestamp or 0.0,
                "speaker": d.participants or "Team",
                "quote": d.evidence_quote or d.decision
            })
            
        grounded_in.extend(["execution_radar", "conflicts", "decisions"])
        return {
            "answer": f"The meeting execution health is rated **{radar['health_status']}** due to the following verifiable factors:\n" + "\n".join(f"• {r}" for r in reasons),
            "evidence": evidence_items,
            "grounded_in": grounded_in
        }

    # 5. Default search across transcript segments
    segments = db.query(TranscriptSegment).filter(TranscriptSegment.meeting_id == meeting_id).all()
    keywords = [w for w in re.sub(r"[^\w\s]", "", q_lower).split() if len(w) > 3]
    matched_segs = []
    for s in segments:
        s_lower = s.text.lower()
        if any(kw in s_lower for kw in keywords):
            matched_segs.append(s)
            
    if matched_segs:
        answers = []
        for s in matched_segs[:3]:
            answers.append(f"[{s.speaker_label}]: \"{s.text}\"")
            evidence_items.append({
                "timestamp": s.start_time,
                "speaker": s.speaker_label,
                "quote": s.text
            })
        grounded_in.append("transcript")
        return {
            "answer": f"Relevant discussion found in meeting recording:\n" + "\n".join(f"• {a}" for a in answers),
            "evidence": evidence_items,
            "grounded_in": grounded_in
        }

    return {
        "answer": f"No direct evidence found in this meeting regarding '{user_question}'. The assistant only provides facts supported by the meeting recording.",
        "evidence": [],
        "grounded_in": []
    }
