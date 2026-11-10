import sys
from src.canvas_client import fetch_active_courses, fetch_course_assignments
from src.watcher import run_watcher
from src.chat_agent import process_handoff
from src.llm import query_nrp

def run_agent(offline: bool = False, db_path: str = "clockwise.db"):
    try:
        watcher_result = run_watcher(
            offline=offline,
            db_path=db_path,
            courses_fn=fetch_active_courses,
            assignments_fn=fetch_course_assignments
        )
    except Exception as e:
        print(f"Watcher execution failed: {e}")
        sys.exit(1)

    status = watcher_result["status"]
    if status == "baseline_saved":
        print(f"Baseline saved ({watcher_result['assignment_count']} assignment(s)). Future runs will report changes.")
        return

    if status == "no_material_changes":
        print("no material changes")
        return

    # Explicit Handoff from WatcherAgent (Agent 1) -> ChatAgent (Agent 2)
    handoff = watcher_result["handoff"]
    print("\n--- Agent Digest ---")
    try:
        result = process_handoff(handoff, db_path=db_path, llm_fn=query_nrp)
        print(result["digest"])
    except Exception as e:
        print(f"LLM call failed: {e}")
    print()
    print(handoff["report"])

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    is_offline = "--offline" in sys.argv
    run_agent(offline=is_offline)