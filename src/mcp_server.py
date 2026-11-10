from fastmcp import FastMCP
from typing import List, Dict, Any
from src.canvas_client import fetch_active_courses, fetch_course_assignments
from src.watcher import run_watcher
from src.state import get_memory, set_memory

mcp = FastMCP("CanvasMCP")

@mcp.tool()
def list_courses() -> List[Dict[str, Any]]:
    """Fetch all active courses for the student."""
    return fetch_active_courses()

@mcp.tool()
def list_assignments(course_id: int) -> List[Dict[str, Any]]:
    """Fetch all assignments for a given course ID."""
    return fetch_course_assignments(course_id)

@mcp.tool()
def get_changes_since_last_run(offline: bool = False) -> Dict[str, Any]:
    """Run WatcherAgent diff engine and return any NEW or DUE_DATE_MOVED triggers."""
    return run_watcher(offline=offline)

@mcp.tool()
def update_notification_preference(preference: str) -> str:
    """Update student triage preference in memory ('all', 'concise', or 'urgent_only')."""
    set_memory("triage_preference", preference)
    return f"Preference updated to {preference}"

if __name__ == "__main__":
    mcp.run()