import os
import requests
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("CANVAS_BASE_URL", "https://fgcu.instructure.com").rstrip("/")
API_TOKEN = os.getenv("CANVAS_TOKEN")


def get_headers(token: Optional[str] = None) -> Dict[str, str]:
    active_token = token or API_TOKEN
    if not active_token:
        raise EnvironmentError("Missing CANVAS_TOKEN.")
    return {
        "Authorization": f"Bearer {active_token}",
        "Accept": "application/json"
    }


def fetch_user_profile(token: Optional[str] = None) -> Dict[str, Any]:
    """Fetches the student's permanent Canvas user ID and name."""
    endpoint = f"{BASE_URL}/api/v1/users/self"
    response = requests.get(endpoint, headers=get_headers(token), timeout=15)
    response.raise_for_status()
    data = response.json()
    return {
        "canvas_uid": str(data["id"]),
        "name": data.get("short_name") or data.get("name") or "Student"
    }


def _get_paginated(url: str, token: Optional[str] = None) -> List[Dict[str, Any]]:
    results = []
    headers = get_headers(token)
    while url:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        results.extend(response.json())
        url = response.links.get("next", {}).get("url")
    return results


def fetch_active_courses(token: Optional[str] = None) -> List[Dict[str, Any]]:
    endpoint = f"{BASE_URL}/api/v1/courses?enrollment_state=active&per_page=50"
    raw_courses = _get_paginated(endpoint, token=token)
    return [
        {
            "id": c.get("id"),
            "name": c.get("name", "Unnamed Course"),
            "course_code": c.get("course_code", "Unknown")
        }
        for c in raw_courses if "id" in c
    ]


def _is_submitted(submission: Dict[str, Any]) -> bool:
    if not submission:
        return False
    if submission.get("excused"):
        return True
    state = submission.get("workflow_state")
    if state in ("submitted", "graded", "pending_review"):
        return True
    return bool(submission.get("submitted_at"))


def fetch_course_assignments(course_id: int, token: Optional[str] = None) -> List[Dict[str, Any]]:
    endpoint = f"{BASE_URL}/api/v1/courses/{course_id}/assignments?include[]=submission&per_page=50"
    raw_assignments = _get_paginated(endpoint, token=token)
    return [
        {
            "id": a.get("id"),
            "course_id": course_id,
            "name": a.get("name", "Untitled Assignment"),
            "due_at": a.get("due_at"),
            "updated_at": a.get("updated_at"),
            "points_possible": a.get("points_possible"),
            "graded": a.get("grading_type") not in ("not_graded", "pass_fail", None) and (a.get("points_possible") or 0) > 0,
            "submitted": _is_submitted(a.get("submission") or {})
        }
        for a in raw_assignments if "id" in a
    ]