import re
import json
import requests
from typing import Dict, Any, List, Tuple, Optional
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

# "bitcoin" and "stock market" were removed: they appear in real course titles and caused wrongful
# refusals. The system prompt still refuses those topics when they are off-topic.
OFF_TOPIC_PATTERNS = re.compile(
    r"\b(ignore (all )?previous instructions|write an essay|write a poem|recipe for|capital of|solve this equation|who won the)\b",
    re.IGNORECASE
)

GUARDRAIL_REFUSAL = "I can only help with your Canvas assignments, deadlines, and notification settings."

ALLOWED_PREFS = ("all", "concise", "urgent_only")

_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_WORD_DATE = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})\b", re.IGNORECASE)
_SLASH_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})\b")


def _dates_in(text: str) -> set:
    found = {(_MONTHS.index(m.group(1)[:3].lower()) + 1, int(m.group(2))) for m in _WORD_DATE.finditer(text or "")}
    found |= {(int(a), int(b)) for a, b in _SLASH_DATE.findall(text or "") if 1 <= int(a) <= 12}
    return found


def dates_grounded(digest: str, triggers: List[Dict[str, Any]]) -> bool:
    """Every date the digest mentions must come from the WatcherAgent payload."""
    allowed = set()
    for t in triggers:
        for key in ("due_at", "old_due_at", "new_due_at"):
            allowed |= _dates_in(t.get(key) or "")
    return _dates_in(digest) <= allowed


def deterministic_digest(triggers: List[Dict[str, Any]]) -> str:
    """Template digest built only from payload fields, used when model output is empty or ungrounded."""
    lines = []
    for t in triggers:
        where = f"{t.get('course_name', t['course_id'])}: {t['name']}"
        if t["event_type"] == "DUE_DATE_MOVED":
            line = f"• [CHANGED] {where} — Now due {t.get('new_due_at')} (was {t.get('old_due_at')})"
        elif t["event_type"] == "NEW":
            line = f"• [NEW] {where} — Due {t.get('due_at')}"
        else:
            line = f"• [DUE SOON] {where} — Due {t.get('due_at')}"
        if t.get("past_due"):
            line += " — PAST DUE"
        lines.append(line)
    return "\n".join(lines) or "No deadline changes detected."


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
        f"Student Notification Preference: {pref}\n"
        f"Canvas Events:\n{json.dumps(triggers, indent=2)}\n\n"
        "Format a clean, easy-to-scan mobile notification using short bullet points (one line per item, max 12 words per line).\n"
        "Use this exact structure for each bullet:\n"
        "• [NEW] Short Course Name: Assignment — Due Date\n"
        "• [CHANGED] Short Course Name: Assignment — Now due New Date\n"
        "• [DUE SOON] Short Course Name: Assignment — Due Date\n"
        "• [PAST DUE] Short Course Name: Assignment — Due Date\n"
        "For Due Date, DO NOT include the day of the week, hours and minutes (e.g. 'MM/DD' instead of 'Mon Nov 04:59 AM').\n"
        "Shorten long course names (e.g. 'Software Engineering' instead of 'CEN-3031-12345 Software Engineering'). "
        "Do not include intro or outro filler text."
    )

    thought_note = None
    try:
        raw_response = llm_fn(prompt) or ""
    except Exception as e:
        raw_response = ""
        thought_note = f"LLM call failed ({type(e).__name__}); used template digest."
    thought, _, digest = _parse_react_output(raw_response)

    if not digest.strip():
        thought = thought_note or "Model returned an empty answer; used template digest."
        digest = deterministic_digest(triggers)
    elif not dates_grounded(digest, triggers):
        thought = f"Model digest mentioned a date not in the payload; replaced with template digest. Model said: {digest!r}"
        digest = deterministic_digest(triggers)
    elif any(t.get("past_due") for t in triggers) and "past due" not in digest.lower():
        digest += "\n" + "\n".join(f"• {t['name']} is PAST DUE" for t in triggers if t.get("past_due"))

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
        new_pref = action.split("=", 1)[1].strip().lower()
        if new_pref in ALLOWED_PREFS:
            set_memory("triage_preference", new_pref, db_path=db_path, user_id=user_id)
        else:
            thought = f"Rejected invalid preference {new_pref!r}; allowed: {', '.join(ALLOWED_PREFS)}."
            answer = (f"I can't set that notification preference. Choose one of: {', '.join(ALLOWED_PREFS)}. "
                      f"Your preference is still '{pref}'.")

    if not answer.strip():
        answer = "Sorry, I couldn't generate an answer just now. Please try again."

    return {
        "thought": thought or "Evaluated student query against Canvas schedule and memory.",
        "answer": answer
    }