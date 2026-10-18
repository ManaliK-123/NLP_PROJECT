import datetime
from typing import Dict, Any, List

def calculate_execution_radar(
    tasks: List[Dict[str, Any]],
    decisions: List[Dict[str, Any]],
    conflicts: List[Dict[str, Any]],
    dependencies: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Computes real-time execution health metrics, risk radar dimensions, and diagnostic evidence.
    """
    total_tasks = len(tasks)
    completed_tasks = sum(1 for t in tasks if t.get("status") == "Completed")
    blocked_tasks = sum(1 for t in tasks if t.get("status") == "Blocked")
    overdue_tasks = sum(1 for t in tasks if t.get("status") == "Overdue")
    clarification_tasks = sum(1 for t in tasks if t.get("status") == "Needs Clarification")
    
    unresolved_decisions = sum(1 for d in decisions if d.get("status") in ("Undecided", "Tentative"))
    conflict_count = len(conflicts)
    
    # Deadline risks: count tasks due within 48h
    now = datetime.datetime.utcnow()
    imminent_deadlines = 0
    for t in tasks:
        norm_dl = t.get("deadline_normalized")
        if norm_dl and isinstance(norm_dl, datetime.datetime):
            delta = (norm_dl - now).total_seconds()
            if 0 <= delta <= 48 * 3600:
                imminent_deadlines += 1

    # Completion & blocked rates
    completion_rate = round((completed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0.0
    blocked_rate = round((blocked_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0.0
    
    # Assess Health Status & compile reasons
    risk_reasons = []
    
    if conflict_count > 0:
        risk_reasons.append(f"{conflict_count} schedule/factual conflict(s) require confirmation.")
    if unresolved_decisions > 0:
        risk_reasons.append(f"{unresolved_decisions} architecture/design decision(s) remain undecided.")
    if blocked_tasks > 0:
        risk_reasons.append(f"{blocked_tasks} task(s) are blocked by dependencies.")
    if clarification_tasks > 0:
        risk_reasons.append(f"{clarification_tasks} commitment(s) lack assigned owners.")
    if imminent_deadlines > 0:
        risk_reasons.append(f"{imminent_deadlines} task deadline(s) fall within next 48 hours.")
        
    if conflict_count >= 2 or blocked_tasks >= 2 or overdue_tasks >= 2:
        health_status = "Critical"
    elif conflict_count > 0 or unresolved_decisions > 0 or blocked_tasks > 0 or clarification_tasks > 0 or imminent_deadlines > 0:
        health_status = "At Risk"
    else:
        health_status = "Healthy"
        risk_reasons.append("All tasks assigned with clear deadlines and no blocking conflicts.")

    # Radar metrics normalized to 0-100 for radar charts
    radar_data = [
        {"subject": "Completion", "score": min(100, int(completion_rate + 20)), "fullMark": 100},
        {"subject": "Ownership Clarity", "score": 90 if clarification_tasks == 0 else 40, "fullMark": 100},
        {"subject": "Decision Velocity", "score": 90 if unresolved_decisions == 0 else 50, "fullMark": 100},
        {"subject": "Alignment (No Conflicts)", "score": 95 if conflict_count == 0 else 35, "fullMark": 100},
        {"subject": "Dependency Flow", "score": 90 if blocked_tasks == 0 else 45, "fullMark": 100},
        {"subject": "Deadline Feasibility", "score": 85 if imminent_deadlines <= 1 else 50, "fullMark": 100},
    ]

    return {
        "health_status": health_status,
        "completion_rate": completion_rate,
        "blocked_rate": blocked_rate,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "blocked_tasks": blocked_tasks,
        "overdue_tasks": overdue_tasks,
        "clarification_tasks": clarification_tasks,
        "unresolved_decisions": unresolved_decisions,
        "conflict_count": conflict_count,
        "imminent_deadlines": imminent_deadlines,
        "reasons": risk_reasons,
        "radar_data": radar_data
    }
