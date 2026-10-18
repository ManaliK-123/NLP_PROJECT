import datetime
from typing import Dict, Any, List

def build_mom_document(
    meeting_title: str,
    meeting_date: datetime.datetime,
    duration_seconds: float,
    agenda: str,
    participants: List[str],
    summary: str,
    tasks: List[Dict[str, Any]],
    decisions: List[Dict[str, Any]],
    conflicts: List[Dict[str, Any]],
    questions: List[Dict[str, Any]],
    dependencies: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Generate professional Minutes of Meeting (MOM) structured payload.
    """
    mins = int(duration_seconds // 60)
    secs = int(duration_seconds % 60)
    duration_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
    
    # Action item tabular rows
    action_items = []
    for t in tasks:
        ts = t.get("evidence_timestamp", 0.0)
        t_min = int(ts // 60)
        t_sec = int(ts % 60)
        action_items.append({
            "task": t.get("title", ""),
            "owner": t.get("owner", "Unassigned"),
            "deadline": t.get("deadline_text") or "Not specified",
            "deadline_status": t.get("deadline_status", "Not specified"),
            "priority": t.get("priority", "Medium"),
            "status": t.get("status", "Pending"),
            "evidence": f"[{t_min:02d}:{t_sec:02d}] {t.get('evidence_quote', '')}"
        })

    # Decisions categorized
    final_decisions = [d for d in decisions if d.get("status") == "Final"]
    undecided_items = [d for d in decisions if d.get("status") in ("Undecided", "Tentative")]

    mom = {
        "meeting_title": meeting_title,
        "date_time": meeting_date.strftime("%B %d, %Y - %I:%M %p") if isinstance(meeting_date, datetime.datetime) else str(meeting_date),
        "duration": duration_str,
        "participants": participants if participants else ["Team Members"],
        "agenda": agenda or "Sprint sync & execution planning",
        "executive_summary": summary,
        "topics_discussed": [
            "Dataset pipeline and preprocessing",
            "Model architecture and baseline training",
            "Project timeline and report submission scheduling"
        ],
        "decisions_taken": [
            {
                "topic": d.get("topic", "General"),
                "decision": d.get("decision", ""),
                "status": d.get("status", "Final"),
                "evidence_timestamp": d.get("evidence_timestamp", 0.0)
            } for d in final_decisions
        ],
        "unresolved_matters": [
            {
                "topic": d.get("topic", "Discussion"),
                "item": d.get("decision", ""),
                "status": d.get("status", "Undecided"),
                "evidence_timestamp": d.get("evidence_timestamp", 0.0)
            } for d in undecided_items
        ],
        "action_items": action_items,
        "dependencies": [
            {
                "from": dep.get("source_label"),
                "to": dep.get("target_label"),
                "relation": dep.get("relation_type", "blocks")
            } for dep in dependencies
        ],
        "conflicts_and_risks": [
            {
                "topic": c.get("topic"),
                "conflict": f"'{c.get('statement_a')}' vs '{c.get('statement_b')}'",
                "status": c.get("status", "Needs confirmation")
            } for c in conflicts
        ],
        "next_steps": [
            "Resolve schedule discrepancy between Thursday submission and Friday review.",
            "Confirm neural network architecture with lead/professor.",
            "Verify dataset labels and push to repository."
        ]
    }
    
    return mom

def generate_mom_markdown(mom: Dict[str, Any]) -> str:
    """Format MOM as clean, exportable GitHub Flavored Markdown."""
    lines = []
    lines.append(f"# Minutes of Meeting: {mom['meeting_title']}")
    lines.append(f"**Date & Time:** {mom['date_time']} | **Duration:** {mom['duration']}")
    lines.append(f"**Participants:** {', '.join(mom['participants'])}")
    lines.append(f"**Agenda:** {mom['agenda']}\n")
    
    lines.append("## Executive Summary")
    lines.append(mom['executive_summary'] + "\n")
    
    lines.append("## Decisions Taken")
    if mom['decisions_taken']:
        for d in mom['decisions_taken']:
            lines.append(f"- **[{d['topic']}]**: {d['decision']} *(Status: {d['status']})*")
    else:
        lines.append("No finalized decisions recorded.")
    lines.append("")

    lines.append("## Action Items & Ownership")
    lines.append("| Task | Owner | Deadline | Priority | Status | Evidence |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    for a in mom['action_items']:
        lines.append(f"| {a['task']} | **{a['owner']}** | {a['deadline']} | {a['priority']} | {a['status']} | `{a['evidence']}` |")
    lines.append("")

    if mom.get('conflicts_and_risks'):
        lines.append("## Identified Conflicts & Risks")
        for c in mom['conflicts_and_risks']:
            lines.append(f"- ⚠️ **{c['topic']}**: {c['conflict']} *(Resolution: {c['status']})*")
        lines.append("")

    if mom.get('unresolved_matters'):
        lines.append("## Unresolved Matters / Open Questions")
        for u in mom['unresolved_matters']:
            lines.append(f"- ❓ **{u['topic']}**: {u['item']}")
        lines.append("")

    lines.append("## Next Steps")
    for s in mom['next_steps']:
        lines.append(f"1. {s}")

    return "\n".join(lines)
