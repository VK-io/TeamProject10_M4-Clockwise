from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

UPCOMING_DAYS = 14

def parse_due(due_at: Optional[str]) -> Optional[datetime]:
    if not due_at:
        return None
    return datetime.fromisoformat(due_at.replace("Z", "+00:00"))

def format_due(due_at: Optional[str]) -> Optional[str]:
    due = parse_due(due_at)
    return due.astimezone().strftime("%a %b %d, %I:%M %p") if due else None

def _fmt(a: Dict[str, Any]) -> str:
    return f"- {a['name'].strip()} ({a.get('course_name', a['course_id'])}) - due {format_due(a['due_at'])}"

def build_report(assignments: List[Dict[str, Any]], now: datetime, days: int = UPCOMING_DAYS) -> str:
    """Deterministic list of upcoming work and unsubmitted past-due graded work."""
    dated = sorted((a for a in assignments if a.get("due_at")), key=lambda a: a["due_at"])
    horizon = now + timedelta(days=days)

    upcoming = [a for a in dated if now <= parse_due(a["due_at"]) <= horizon and not a.get("submitted")]
    past_due = [
        a for a in dated
        if parse_due(a["due_at"]) < now and a.get("graded", True) and not a.get("submitted")
    ]

    lines = [f"Coming up (next {days} days):"]
    lines += [_fmt(a) for a in upcoming] or ["- Nothing due."]
    lines += ["", "PAST DUE (graded, not submitted):"]
    lines += [_fmt(a) + " - PAST DUE" for a in past_due] or ["- None."]
    return "\n".join(lines)
