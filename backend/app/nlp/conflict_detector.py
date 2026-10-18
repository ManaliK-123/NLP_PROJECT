import re
from typing import List, Dict, Any

CONFLICT_PATTERNS = [
    r"\b(?:actually|no|wait|contrary to|instead of|not\s+[a-z]+,?\s*but|rather than)\b",
    r"\b(?:is\s+([a-zA-Z]+),?\s*not\s+([a-zA-Z]+))\b"
]

DAYS_OF_WEEK = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}

def detect_conflicts(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Detect contradictory statements across meeting segments with dual evidence tracing.
    """
    conflicts = []
    
    for i, seg in enumerate(segments):
        text = seg["text"]
        lower = text.lower()
        
        # 1. Explicit correction syntax like:
        # "actually, the report submission is Thursday, not Friday."
        # or "No, we should use B, not A"
        correction_match = re.search(r"\b(?:actually|wait,?\s*actually|no,?\s*the|instead)\s+(?:the\s+)?([a-zA-Z\s]+?)\s+is\s+([a-zA-Z0-9\s]+?),\s*not\s+([a-zA-Z0-9\s]+)", lower)
        if correction_match:
            item = correction_match.group(1).strip()
            new_val = correction_match.group(2).strip()
            old_val = correction_match.group(3).strip()
            
            # Find the earlier segment that mentioned the old value
            earlier_seg = None
            for prev_idx in range(i - 1, -1, -1):
                if old_val in segments[prev_idx]["text"].lower():
                    earlier_seg = segments[prev_idx]
                    break
                    
            statement_a = earlier_seg["text"] if earlier_seg else f"Mentioned {old_val} earlier in discussion"
            speaker_a = earlier_seg["speaker_label"] if earlier_seg else "Previous Speaker"
            timestamp_a = earlier_seg["start_time"] if earlier_seg else max(0.0, seg["start_time"] - 10.0)
            
            conflicts.append({
                "topic": f"{item.capitalize()} Schedule Discrepancy",
                "statement_a": statement_a,
                "speaker_a": speaker_a,
                "timestamp_a": timestamp_a,
                "statement_b": text,
                "speaker_b": seg.get("speaker_label", "Speaker"),
                "timestamp_b": seg["start_time"],
                "status": "Needs confirmation",
                "resolution": f"Confirmation required between '{new_val}' vs '{old_val}'"
            })
            continue

        # 2. Epistemic contradiction: "I thought it was Friday" or "Wait, isn't it Friday?"
        epistemic_match = re.search(r"\b(?:i thought (?:it was|that was)|wait,?\s*(?:isn't it|i thought)|wasn't it|isn't it supposed to be)\s+([a-zA-Z0-9\s]+)", lower)
        if epistemic_match:
            claimed_val = epistemic_match.group(1).strip().rstrip(".?!")
            # Look backwards for preceding segment mentioning a competing day/deadline
            earlier_seg = None
            competing_val = None
            
            for prev_idx in range(i - 1, -1, -1):
                prev_text = segments[prev_idx]["text"]
                prev_lower = prev_text.lower()
                # Check for days of week or deadline words
                for day in DAYS_OF_WEEK:
                    if day in prev_lower and day not in claimed_val:
                        earlier_seg = segments[prev_idx]
                        competing_val = day.capitalize()
                        break
                if earlier_seg:
                    break

            if earlier_seg:
                topic = "Report Submission Deadline" if "report" in earlier_seg["text"].lower() or "report" in lower else "Schedule Discrepancy"
                conflicts.append({
                    "topic": topic,
                    "statement_a": earlier_seg["text"],
                    "speaker_a": earlier_seg.get("speaker_label", "Speaker"),
                    "timestamp_a": earlier_seg["start_time"],
                    "statement_b": text,
                    "speaker_b": seg.get("speaker_label", "Speaker"),
                    "timestamp_b": seg["start_time"],
                    "status": "Needs confirmation",
                    "resolution": f"Confirmation required: {competing_val} vs {claimed_val.capitalize()}"
                })
                continue

        # 3. Explicit "not [day]" syntax: "Report is due Thursday, not Friday"
        for day in DAYS_OF_WEEK:
            if f"not {day}" in lower:
                earlier_seg = None
                for prev_idx in range(i - 1, -1, -1):
                    if day in segments[prev_idx]["text"].lower():
                        earlier_seg = segments[prev_idx]
                        break
                if earlier_seg:
                    conflicts.append({
                        "topic": "Report Submission Deadline",
                        "statement_a": earlier_seg["text"],
                        "speaker_a": earlier_seg.get("speaker_label", "Speaker"),
                        "timestamp_a": earlier_seg["start_time"],
                        "statement_b": text,
                        "speaker_b": seg.get("speaker_label", "Speaker"),
                        "timestamp_b": seg["start_time"],
                        "status": "Needs confirmation",
                        "resolution": f"Action required: Confirm official deadline ({day.capitalize()})."
                    })
                    break

    return conflicts

