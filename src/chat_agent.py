import re
import json
import requests
from typing import Dict, Any, Tuple, Optional
from src.state import get_memory, set_memory, _get_secret, DB_PATH

SYSTEM_GUARDRAIL = """You are Clockwise (Frontend Advisor Agent), an AI assistant strictly scoped to the student's Canvas courses, assignments, deadlines, and notification preferences.

STRICT GUARDRAIL:
If the user asks about anything outside of their Canvas coursework, deadlines, schedule, or notification preferences (such as general trivia, writing essays, solving math/coding problems, politics, or recipes), you MUST refuse immediately with:
"I can only help with your Canvas assignments, deadlines, and notification settings."

REASONING PATTERN (ReAct / Chain-of-Thought):
Always structure your response in two parts:
THOUGHT: Reason step-by-step about the student's preference in memory, the assignment data or change events, and whether the query passes the guardrail.
ACTION_MEMORY: (Optional) Write SET_PREF=all, SET_PREF=concise, or SET_PREF=urgent_only ONLY if the user explicitly asks to change how they are notified. Otherwise write NONE.
ANSWER: Your concise, helpful response to the student (2-3 sentences max).
"""

OFF_TOPIC_PATTERNS = re.compile(
    r"\b(ignore previous instructions|write an essay|write a poem|recipe for|capital of|solve this equation|who won the|bitcoin|stock market)\b",
    re.IGNORECASE
)

GUARDRAIL_REFUSAL = "I can only help with your Canvas assignments, deadlines, and notification settings."


def _parse_react_output(raw_output: str) -> Tuple[str, str, str]:
    thought = ""
    action = "NONE"
    answer = raw_output.strip()

    if "ANSWER:" in raw_output:
        parts = raw_output.split("ANSWER:", 1)
        header = parts[0]
        answer = parts[1].strip()
        if "THOUGHT:" in header:
            thought = header.split("THOUGHT:", 1)[1].split("ACTION_MEMORY:")[0].strip()
        if "ACTION_MEMORY:" in header:
            action = header.split("ACTION_MEMORY:", 1)[1].strip().splitlines()[0].strip()

    return thought, action, answer


def send_push_notification(message: str, topic: Optional[str] = None) -> bool:
    target_topic = (topic or _get_secret("NTFY_TOPIC", "")).strip()
    if not target_topic:
        return False
    app_url = _get_secret("APP_URL", "")
    headers = {"Title": "Clockwise Canvas Alert"}
    if app_url:
        headers["Click"] = app_url
    try:
        requests.post(
            f"https://ntfy.sh/{target_topic}",
            data=message.encode("utf-8"),
            headers=headers,
            timeout=5
        )
        return True
    except Exception:
        return False


def process_handoff(
    handoff_payload: Dict[str, Any],
    db_path: str = DB_PATH,
    user_id: str = "default",
    ntfy_topic: Optional[str] = None,
    llm_fn=None
) -> Dict[str, str]:
    if llm_fn is None:
        from src.llm import query_nrp
        llm_fn = query_nrp

    triggers = handoff_payload.get("triggers", [])
    pref = get_memory("triage_preference", default="concise", db_path=db_path, user_id=user_id)

    prompt = (
        f"Student Notification Preference (from Memory): {pref}\n"
        f"Detected Canvas events (NEW, DUE_DATE_MOVED, REMINDER_3_DAY, REMINDER_1_DAY):\n{json.dumps(triggers, indent=2)}\n\n"
        "Draft a clear 2-3 sentence notification summarizing these alerts for a busy student. "
        "Refer to courses by course_name. Explicitly label items as NEW, CHANGED (with old -> new date), "
        "or DUE SOON (for 3-day or 1-day reminders), and say PAST DUE for any item where past_due is true. "
        "Only describe the listed changes; do not make claims about any other assignments."
    )

    raw_response = llm_fn(prompt)
    thought, _, digest = _parse_react_output(raw_response)

    set_memory("last_digest", digest, db_path=db_path, user_id=user_id)
    send_push_notification(digest, topic=ntfy_topic)

    return {
        "thought": thought or f"Evaluated {len(triggers)} trigger(s) under '{pref}' preference.",
        "digest": digest
    }


def handle_user_chat(
    user_message: str,
    db_path: str = DB_PATH,
    user_id: str = "default",
    llm_fn=None
) -> Dict[str, str]:
    if llm_fn is None:
        from src.llm import query_nrp
        llm_fn = query_nrp

    if OFF_TOPIC_PATTERNS.search(user_message):
        return {
            "thought": "Blocked by pre-LLM input guardrail.",
            "answer": GUARDRAIL_REFUSAL
        }

    pref = get_memory("triage_preference", default="concise", db_path=db_path, user_id=user_id)
    last_digest = get_memory("last_digest", default="No recent deadline changes detected.", db_path=db_path, user_id=user_id)
    latest_report = get_memory("latest_report", default="No schedule report generated yet.", db_path=db_path, user_id=user_id)

    prompt = (
        f"--- MEMORY CONTEXT ---\n"
        f"Current Notification Preference: {pref}\n"
        f"Most Recent Change Digest: {last_digest}\n"
        f"Current 14-Day & Past-Due Report:\n{latest_report}\n"
        f"----------------------\n\n"
        f"Student Message: {user_message}"
    )

    try:
        raw_response = llm_fn(prompt, system_prompt=SYSTEM_GUARDRAIL)
    except TypeError:
        raw_response = llm_fn(f"{SYSTEM_GUARDRAIL}\n\n{prompt}")

    thought, action, answer = _parse_react_output(raw_response)

    if action.startswith("SET_PREF="):
        new_pref = action.split("=", 1)[1].strip()
        set_memory("triage_preference", new_pref, db_path=db_path, user_id=user_id)

    return {
        "thought": thought or "Evaluated student query against Canvas schedule and memory.",
        "answer": answer
    }