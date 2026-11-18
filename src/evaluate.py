"""Clockwise evaluation runner (M3 plan -> M4 results).

Usage:
    python -m src.evaluate                 # mock LLM: checks the pipeline, watcher and guardrails only
    python -m src.evaluate --live          # real NRP model + critic agent (needs NRP_API_KEY)
    python -m src.evaluate --live --runs 5 --label final

Writes eval/results_<label>.csv, eval/results_<label>.md and eval/summary_<label>.json.
"""
import argparse
import copy
import csv
import json
import os
import re
import statistics
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from zoneinfo import ZoneInfo

from src.chat_agent import GUARDRAIL_REFUSAL, handle_user_chat, process_handoff
from src.critic import critique
from src.report import parse_due
from src.state import get_memory
from src.watcher import run_watcher

CASES_FILE = Path("tests/eval_cases.json")
OUT_DIR = Path("eval")
CRITIC_PASS = 4.0


# ---------- LLM backends ----------

class CountingLLM:
    """Wraps an llm_fn, counts calls and remembers the last raw output."""

    def __init__(self, fn: Callable[..., str]):
        self.fn, self.calls, self.last = fn, 0, None

    def __call__(self, prompt: str, *args, **kwargs) -> str:
        self.calls += 1
        self.last = self.fn(prompt, *args, **kwargs)
        return self.last


def mock_llm(prompt: str, system_prompt: str = "", **_) -> str:
    """Deterministic stand-in for the model so the pipeline can be checked without an API key.
    It does NOT measure language quality; only --live does."""
    m = re.search(r"Canvas Events:\n(.*?)\n\nFormat", prompt, re.DOTALL)
    if m:
        parts = []
        for t in json.loads(m.group(1)):
            if t["event_type"] == "DUE_DATE_MOVED":
                parts.append(f"CHANGED: {t['name']} ({t['course_name']}) moved {t['old_due_at']} -> {t['new_due_at']}.")
            elif t["event_type"].startswith("REMINDER"):
                parts.append(f"DUE SOON: {t['name']} ({t['course_name']}) due {t['due_at']}.")
            else:
                parts.append(f"NEW: {t['name']} ({t['course_name']}) due {t['due_at']}.")
            if t.get("past_due"):
                parts.append(f"{t['name']} is PAST DUE.")
        return " ".join(parts)
    msg = prompt.rsplit("Student Message:", 1)[-1].lower()
    if "urgent" in msg:
        return "THOUGHT: wants urgent only\nACTION_MEMORY: SET_PREF=urgent_only\nANSWER: Done - you'll only get urgent alerts now."
    return "THOUGHT: schedule question\nACTION_MEMORY: NONE\nANSWER: Here is what I found in your Canvas schedule."


def live_llm(prompt: str, system_prompt: Optional[str] = None, **_) -> str:
    from src.llm import query_nrp
    return query_nrp(prompt, system_prompt) if system_prompt else query_nrp(prompt)


# ---------- feed construction ----------

def _materialize(items: List[Dict[str, Any]], now: datetime) -> List[Dict[str, Any]]:
    out = []
    for it in items:
        a = {k: v for k, v in it.items() if k != "due_offset_days"}
        due = now + timedelta(days=it["due_offset_days"])
        a["due_at"] = due.replace(hour=23, minute=59, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
        a.setdefault("graded", True)
        a.setdefault("submitted", False)
        out.append(a)
    return out


def _apply(feed: List[Dict[str, Any]], step: Any, base: List[Dict[str, Any]], now: datetime) -> List[Dict[str, Any]]:
    if step == "base":
        return _materialize(base, now)
    feed = copy.deepcopy(feed)
    if "move" in step:
        for a in feed:
            if a["id"] == step["move"]["id"]:
                a["due_at"] = (parse_due(a["due_at"]) + timedelta(days=step["move"]["by_days"])).strftime("%Y-%m-%dT%H:%M:%SZ")
    if "add" in step:
        feed += _materialize([step["add"]], now)
    if "remove" in step:
        feed = [a for a in feed if a["id"] != step["remove"]["id"]]
    return feed


def _date_variants(iso: Optional[str]) -> List[str]:
    """Ways a model may legitimately write a date: 'Nov 24', 'November 24', '11/24'."""
    d = parse_due(iso)
    if not d:
        return []
    d = d.astimezone(ZoneInfo("America/New_York"))
    return [d.strftime("%b %d"), d.strftime("%B %d"), f"{d.strftime('%b')} {d.day}", f"{d.strftime('%B')} {d.day}", f"{d.month}/{d.day}"]


def _keywords_ok(text: str, keywords: List[str], new_due: Optional[str]) -> List[str]:
    """Returns the list of missing keywords."""
    missing = []
    low = text.lower()
    for kw in keywords:
        options = _date_variants(new_due) if kw == "{new_date}" else [kw]
        if not any(o.lower() in low for o in options):
            missing.append(options[0] if options else kw)
    return missing


# ---------- case runners ----------

def run_watcher_case(case: Dict[str, Any], spec: Dict[str, Any], llm: CountingLLM, live: bool) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    courses = spec["courses"]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = str(Path(tmp) / "eval.db")
        feed: List[Dict[str, Any]] = []
        result = None
        for step in case["polls"]:
            feed = _apply(feed, step, spec["base"], now)
            snapshot = copy.deepcopy(feed)
            result = run_watcher(
                offline=False, db_path=db,
                courses_fn=lambda: courses,
                assignments_fn=lambda cid, s=snapshot: [copy.deepcopy(a) for a in s if a["course_id"] == cid],
            )
            if result["handoff"]:
                process_handoff(result["handoff"], db_path=db, llm_fn=llm)
        digest = get_memory("last_digest", default="", db_path=db) if result["handoff"] else ""

    checks, notes = [], []
    checks.append(result["status"] == case["expect_status"])
    notes.append(f"status={result['status']}")
    if "expect_llm_calls" in case:
        checks.append(llm.calls == case["expect_llm_calls"])
        notes.append(f"llm_calls={llm.calls}")
    triggers = result["handoff"]["triggers"] if result["handoff"] else []
    new_due = None
    if case.get("expect_event"):
        ev = [t for t in triggers if t["event_type"] == case["expect_event"]]
        checks.append(bool(ev))
        notes.append(f"events={[t['event_type'] for t in triggers]}")
        if ev:
            new_due = next((a["due_at"] for a in feed if a["id"] == ev[0]["assignment_id"]), None)
    elif triggers:
        new_due = next((a["due_at"] for a in feed if a["id"] == triggers[0]["assignment_id"]), None)
    if "expect_past_due" in case:
        flag = any(t.get("past_due") for t in triggers)
        checks.append(flag == case["expect_past_due"])
        notes.append(f"past_due={flag}")
    if case.get("expect_keywords"):
        missing = _keywords_ok(digest, case["expect_keywords"], new_due)
        checks.append(not missing)
        if missing:
            notes.append(f"missing keywords={missing}")
    for bad in case.get("forbid_keywords", []):
        if bad.lower() in digest.lower():
            checks.append(False)
            notes.append(f"forbidden keyword present={bad!r}")

    crit = None
    if live and case.get("use_critic") and digest:
        crit = critique(digest, triggers, llm_fn=live_llm)
        notes.append(f"critic: {crit.get('reason', '')}")

    return {"actual": digest or f"(no digest) status={result['status']}", "passed": all(checks),
            "critic": crit, "notes": "; ".join(notes)}


def run_chat_case(case: Dict[str, Any], llm: CountingLLM) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = str(Path(tmp) / "eval.db")
        res = handle_user_chat(case["message"], db_path=db, llm_fn=llm)
        pref = get_memory("triage_preference", default="concise", db_path=db)
    answer = res["answer"]
    checks, notes = [], [f"llm_calls={llm.calls}", f"pref={pref}"]
    if "expect_refusal" in case:
        checks.append((answer == GUARDRAIL_REFUSAL) == case["expect_refusal"])
    if "expect_llm_calls" in case:
        checks.append(llm.calls == case["expect_llm_calls"])
    if "expect_pref" in case:
        checks.append(pref == case["expect_pref"])
    if case.get("expect_keywords_any"):
        ok = any(k.lower() in answer.lower() for k in case["expect_keywords_any"])
        checks.append(ok)
        if not ok:
            notes.append(f"reply missing any of {case['expect_keywords_any']}")
    return {"actual": answer, "passed": all(checks), "critic": None, "notes": "; ".join(notes)}


def suspected_cause(case: Dict[str, Any], row: Dict[str, Any]) -> str:
    if row["passed"]:
        return ""
    n = row["notes"]
    if "status=" in n and case.get("expect_status") and f"status={case['expect_status']}" not in n:
        return "watcher logic"
    if case["type"] == "chat" and "expect_pref" in case:
        return "memory guardrail"
    if case["type"] == "chat":
        return "input guardrail"
    if "forbidden" in n or "missing keywords" in n:
        return "prompt / reasoning (digest content)"
    if row.get("critic_mean") is not None and row["critic_mean"] < CRITIC_PASS:
        return "prompt (critic score below 4)"
    return "other"


def run_case(case: Dict[str, Any], spec: Dict[str, Any], live: bool, runs: int) -> Dict[str, Any]:
    n = runs if (live and case.get("use_critic")) else 1
    results = []
    for _ in range(n):
        if "forced_model_output" in case:
            fn = lambda *a, out=case["forced_model_output"], **k: out
        else:
            fn = live_llm if live else mock_llm
        llm = CountingLLM(fn)
        try:
            r = run_watcher_case(case, spec, llm, live) if case["type"] == "watcher" else run_chat_case(case, llm)
        except Exception as e:  # a crash is a failed case, not a crashed suite
            r = {"actual": f"ERROR: {type(e).__name__}: {e}", "passed": False, "critic": None, "notes": "exception"}
        results.append(r)

    scores = [r["critic"]["score"] for r in results if r["critic"] and r["critic"].get("score") is not None]
    critic_mean = round(statistics.mean(scores), 2) if scores else None
    passed = all(r["passed"] for r in results)
    if live and case.get("use_critic"):
        passed = passed and critic_mean is not None and critic_mean >= CRITIC_PASS
    row = {
        "id": case["id"], "title": case["title"], "input": case["input"], "expected": case["expected"],
        "judge": case["judge"], "critical": case.get("critical", False),
        "actual": results[0]["actual"], "passed": passed, "runs": n,
        "runs_passed": sum(r["passed"] for r in results),
        "critic_scores": scores, "critic_mean": critic_mean,
        "notes": " | ".join(dict.fromkeys(r["notes"] for r in results)),
    }
    row["suspected_cause"] = suspected_cause(case, row)
    return row


# ---------- output ----------

def _md_cell(s: Any) -> str:
    return str(s).replace("|", "\\|").replace("\n", "<br>")


def write_outputs(rows: List[Dict[str, Any]], supp: List[Dict[str, Any]], label: str, live: bool) -> Dict[str, Any]:
    OUT_DIR.mkdir(exist_ok=True)
    core_passed = sum(r["passed"] for r in rows)
    critical_ok = all(r["passed"] for r in rows if r["critical"])
    critic_all = [s for r in rows for s in r["critic_scores"]]
    summary = {
        "label": label, "mode": "live" if live else "mock", "run_at": datetime.now(timezone.utc).isoformat(),
        "model": os.getenv("NRP_MODEL", "gpt-oss") if live else "mock",
        "core_passed": core_passed, "core_total": len(rows),
        "pass_rate": round(100 * core_passed / len(rows), 1),
        "critical_cases_all_pass": critical_ok,
        "critic_mean": round(statistics.mean(critic_all), 2) if critic_all else None,
        "meets_threshold": core_passed >= 9 and critical_ok and (not live or (critic_all and statistics.mean(critic_all) >= CRITIC_PASS)),
        "supplementary_passed": sum(r["passed"] for r in supp), "supplementary_total": len(supp),
    }
    fields = ["id", "title", "input", "expected", "actual", "passed", "critic_mean", "critic_scores",
              "runs_passed", "runs", "judge", "critical", "suspected_cause", "notes"]
    with open(OUT_DIR / f"results_{label}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows + supp:
            w.writerow({k: ("PASS" if r[k] else "FAIL") if k == "passed" else r[k] for k in fields})

    lines = [f"# Clockwise evaluation results: `{label}` ({summary['mode']} mode)", "",
             f"Run at {summary['run_at']} · model: {summary['model']}", "",
             f"**Core pass rate: {core_passed}/{len(rows)} ({summary['pass_rate']}%)** · "
             f"critical cases (TC01, 02, 05, 07, 08, 10) all pass: **{critical_ok}** · "
             f"critic mean: **{summary['critic_mean']}** · meets M3 threshold: **{summary['meets_threshold']}**", ""]
    if not live:
        lines += ["> Mock mode: the LLM is a deterministic stub, so digest wording is not being evaluated "
                  "and no critic scores are produced. Run with `--live` for the graded results.", ""]
    head = "| ID | Input | Expected | Actual | Result | Critic | Suspected cause |"
    sep = "|---|---|---|---|---|---|---|"
    lines += ["## Core test cases (committed in M3)", "", head, sep]
    for r in rows:
        lines.append("| " + " | ".join(_md_cell(x) for x in [r["id"], r["input"], r["expected"], r["actual"],
                     "PASS" if r["passed"] else "FAIL", r["critic_mean"] if r["critic_mean"] is not None else "n/a",
                     r["suspected_cause"]]) + " |")
    lines += ["", "## Supplementary cases (added in M4 for M3's named failure modes)", "", head, sep]
    for r in supp:
        lines.append("| " + " | ".join(_md_cell(x) for x in [r["id"], r["input"], r["expected"], r["actual"],
                     "PASS" if r["passed"] else "FAIL", "n/a", r["suspected_cause"]]) + " |")
    lines += ["", "## Check notes", ""] + [f"- **{r['id']}**: {r['notes']}" for r in rows + supp]
    (OUT_DIR / f"results_{label}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT_DIR / f"summary_{label}.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    ap = argparse.ArgumentParser(description="Run the Clockwise evaluation suite.")
    ap.add_argument("--live", action="store_true", help="use the real NRP model and the critic agent")
    ap.add_argument("--runs", type=int, default=5, help="live runs per critic-graded case (default 5)")
    ap.add_argument("--label", default=None, help="output file label (default: live or mock)")
    args = ap.parse_args()
    os.environ.pop("NTFY_TOPIC", None)  # never push real notifications during evaluation

    spec = json.loads(CASES_FILE.read_text())
    rows = [run_case(c, spec, args.live, args.runs) for c in spec["cases"]]
    supp = [run_case(c, spec, args.live, 1) for c in spec.get("supplementary", [])]
    label = args.label or ("live" if args.live else "mock")
    summary = write_outputs(rows, supp, label, args.live)

    for r in rows + supp:
        crit = f" critic={r['critic_mean']}" if r["critic_mean"] is not None else ""
        print(f"{r['id']:5} {'PASS' if r['passed'] else 'FAIL'}{crit}  {r['title']}")
    print(f"\nCore: {summary['core_passed']}/{summary['core_total']} ({summary['pass_rate']}%) | "
          f"critical all pass: {summary['critical_cases_all_pass']} | meets threshold: {summary['meets_threshold']}")
    print(f"Wrote {OUT_DIR}/results_{label}.csv, .md and summary_{label}.json")


if __name__ == "__main__":
    main()
