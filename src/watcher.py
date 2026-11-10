import sys
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from src.canvas_client import fetch_active_courses, fetch_course_assignments
from src.state import (
    compute_diff_and_update, has_snapshot, enqueue_handoff,
    set_memory, list_all_users, update_sync_status, DB_PATH
)
from src.report import parse_due, format_due, build_report

NOTIFY_EVENTS = ("NEW", "DUE_DATE_MOVED", "REMINDER_3_DAY", "REMINDER_1_DAY")


def run_watcher(
    offline: bool = False,
    db_path: str = DB_PATH,
    user_id: str = "default",
    canvas_token: Optional[str] = None,
    courses_fn=fetch_active_courses,
    assignments_fn=fetch_course_assignments
) -> Dict[str, Any]:
    assignments_data = []

    try:
        if offline:
            fixtures_dir = Path("tests/fixtures")
            with open(fixtures_dir / "assignments.json") as f:
                assignments_data = json.load(f)
            with open(fixtures_dir / "courses.json") as f:
                courses = json.load(f)
        else:
            courses = courses_fn(token=canvas_token) if canvas_token else courses_fn()
            for course in courses:
                c_assignments = (
                    assignments_fn(course["id"], token=canvas_token)
                    if canvas_token else assignments_fn(course["id"])
                )
                assignments_data.extend(c_assignments)
        update_sync_status(user_id, "ok", db_path=db_path)
    except Exception as e:
        update_sync_status(user_id, f"error: {e}", db_path=db_path)
        raise

    course_names = {c["id"]: c["name"] for c in courses}
    for a in assignments_data:
        a["course_name"] = course_names.get(a["course_id"], str(a["course_id"]))

    now = datetime.now(timezone.utc)
    first_run = not has_snapshot(db_path, user_id=user_id)
    changes = compute_diff_and_update(assignments_data, db_path=db_path, user_id=user_id, now=now)
    report_text = build_report(assignments_data, now)

    set_memory("latest_assignments", assignments_data, db_path=db_path, user_id=user_id)
    set_memory("latest_report", report_text, db_path=db_path, user_id=user_id)

    if first_run:
        return {"status": "baseline_saved", "assignment_count": len(assignments_data), "handoff": None}

    triggers = [c for c in changes if c["event_type"] in NOTIFY_EVENTS]
    if not triggers:
        return {"status": "no_material_changes", "assignment_count": len(assignments_data), "handoff": None}

    for c in triggers:
        c["course_name"] = course_names.get(c["course_id"], str(c["course_id"]))
        due = parse_due(c.get("due_at") or c.get("new_due_at"))
        c["past_due"] = bool(due and due < now)
        for key in ("due_at", "old_due_at", "new_due_at"):
            if key in c:
                c[key] = format_due(c[key])

    handoff_payload = {
        "from_agent": "WatcherAgent",
        "to_agent": "ChatAgent",
        "user_id": user_id,
        "timestamp": now.isoformat(),
        "triggers": triggers,
        "report": report_text
    }
    enqueue_handoff(handoff_payload, db_path=db_path, user_id=user_id)

    return {"status": "handoff_created", "assignment_count": len(assignments_data), "handoff": handoff_payload}


if __name__ == "__main__":
    if "--all-users" in sys.argv:
        from src.chat_agent import process_handoff
        users = list_all_users()
        print(f"Running daily poll for {len(users)} registered user(s)...")
        for u in users:
            try:
                res = run_watcher(user_id=u["user_id"], canvas_token=u["canvas_token"])
                if res["status"] == "handoff_created":
                    process_handoff(res["handoff"], user_id=u["user_id"], ntfy_topic=u["ntfy_topic"])
                    print(f"[{u['user_id']}] Notification sent.")
                else:
                    print(f"[{u['user_id']}] {res['status']}")
            except Exception as err:
                print(f"[{u['user_id']}] Sync error: {err}")