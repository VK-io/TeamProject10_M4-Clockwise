"""Critic agent: a second LLM call that grades a ChatAgent digest against the
WatcherAgent payload it was written from (M3 evaluation plan, Ch.7 critic pattern)."""
import json
import re
from typing import Any, Dict, List

CRITIC_SYSTEM = (
    "You are a strict evaluator of student deadline alerts. You compare an alert "
    "against the ground-truth change events it was generated from. You reply with JSON only."
)

CRITIC_PROMPT = """Ground-truth change events (JSON):
{events}

Alert sent to the student:
\"\"\"{digest}\"\"\"

Score the alert from 1 (bad) to 5 (excellent) on:
- accuracy: every assignment name, course and date matches the events; nothing invented; PAST DUE stated when past_due is true.
- clarity: a tired student understands immediately what changed and what to do.
- brevity: 2-3 sentences, no filler.

Reply with exactly one JSON object:
{{"accuracy": <1-5>, "clarity": <1-5>, "brevity": <1-5>, "score": <overall 1-5>, "reason": "<one sentence>"}}"""


def _parse(raw: str) -> Dict[str, Any]:
    match = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if not match:
        return {"score": None, "reason": f"unparseable critic output: {raw[:120]!r}"}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"score": None, "reason": f"invalid critic JSON: {match.group(0)[:120]!r}"}
    try:
        data["score"] = float(data.get("score"))
    except (TypeError, ValueError):
        data["score"] = None
    return data


def critique(digest: str, triggers: List[Dict[str, Any]], llm_fn=None) -> Dict[str, Any]:
    """Returns {"accuracy", "clarity", "brevity", "score", "reason"}; score is None on failure."""
    if llm_fn is None:
        from src.llm import query_nrp
        llm_fn = query_nrp
    prompt = CRITIC_PROMPT.format(events=json.dumps(triggers, indent=2), digest=digest)
    return _parse(llm_fn(prompt, system_prompt=CRITIC_SYSTEM))
