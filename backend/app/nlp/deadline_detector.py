import re
import datetime
from typing import Optional, Tuple, Dict, Any
import dateparser

TEMPORAL_PATTERNS = [
    r"\b(?:by|before|until|due|on|within|deadline is)\s+([a-zA-Z0-9\s,\.-]+?)(?=[,\.\?!;]|$|\band\b)",
    r"\b(today|tomorrow|tonight|asap|end of week|next week|eod)\b",
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    r"\bwithin\s+(\d+)\s+(days?|hours?|weeks?)\b"
]

AMBIGUOUS_KEYWORDS = {"soon", "asap", "later", "shortly", "eventually", "before submission", "after meeting", "when ready"}

def detect_deadline(text: str, reference_date: Optional[datetime.datetime] = None) -> Dict[str, Any]:
    """
    Extract temporal expression, determine status (Exact, Ambiguous, Not specified),
    and normalize relative to reference_date.
    """
    if reference_date is None:
        reference_date = datetime.datetime.utcnow()

    lower_text = text.lower()
    
    # 1. Check for ambiguous phrases first
    for kw in AMBIGUOUS_KEYWORDS:
        if kw in lower_text:
            return {
                "deadline_text": kw.upper() if kw == "asap" else kw.capitalize(),
                "deadline_normalized": None,
                "deadline_status": "Ambiguous"
            }

    # 2. Match regex patterns
    matched_phrase = None
    for pattern in TEMPORAL_PATTERNS:
        match = re.search(pattern, lower_text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            # Filter out non-temporal false positives
            if candidate and len(candidate) > 1 and not re.match(r"^(the|a|an|it|this|that|us|we|our|all|some)$", candidate):
                matched_phrase = candidate
                break

    if not matched_phrase:
        return {
            "deadline_text": None,
            "deadline_normalized": None,
            "deadline_status": "Not specified"
        }

    # Clean matched phrase
    cleaned_phrase = re.sub(r"^(the|next)\s+", "", matched_phrase).strip()

    # 3. Parse with dateparser using reference date
    settings = {
        "RELATIVE_BASE": reference_date,
        "PREFER_DATES_FROM": "future",
        "RETURN_AS_TIMEZONE_AWARE": False
    }

    parsed = dateparser.parse(matched_phrase, settings=settings)
    
    if parsed:
        # If parsed date is in the past relative to reference_date, bump by 7 days if day of week was matched
        if parsed < reference_date:
            parsed += datetime.timedelta(days=7)
            
        return {
            "deadline_text": matched_phrase.capitalize(),
            "deadline_normalized": parsed,
            "deadline_status": "Exact"
        }
    
    # Fallback to ambiguous if temporal words exist but exact date cannot be fixed
    return {
        "deadline_text": matched_phrase.capitalize(),
        "deadline_normalized": None,
        "deadline_status": "Ambiguous"
    }
