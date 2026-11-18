# Clockwise: M4 Report

*CEN 4930 · Team 10 · Evaluated + User-Tested Agent*

> `[TODO]` marks every spot that still needs data from the team. **Don't submit with any left.**

## Team
| Member | Background | M4 contributions |
|---|---|---|
| [TODO] | | |
| [TODO] | | |
| [TODO] | | |

---

## Part 1: Evaluation Results

### 1.1 Method (as committed in M3)
- **TDAD exact-match checks** for the deterministic half: WatcherAgent status, handoff payload, guardrails and memory state.
- **Critic agent** (`src/critic.py`) for the free-text half: a second LLM call scores each ChatAgent digest 1–5 on accuracy against the event JSON, clarity and brevity; ≥4 passes. Cases 3, 4 and 6 run 5 times each in live mode.
- **Threshold:** ≥9/10 overall; cases 1, 2, 5, 7, 8 and 10 must pass; critic mean ≥4.0.
- **Supplementary cases S01–S03** cover the failure modes M3 said the suite would not catch (wrongful refusal, empty output, hallucinated date). They are reported separately so the committed 10-case pass rate is unchanged.
- **Honesty note:** the M3 report described `src/evaluate.py`, `tests/eval_cases.json` and the critic as existing, and cited 17 unit tests; in fact they did not exist yet and there were 14 tests. All of them were built for M4 (see commit history), and the suite now has 22 tests.

Harness: `python -m src.evaluate [--live]` → `eval/results_<label>.csv`, `.md` and `summary_<label>.json`.

### 1.2 Results

| Run | Core pass rate | Critical cases | Critic mean | Supplementary |
|---|---|---|---|---|
| Baseline, pre-fix code, mock LLM (`eval/results_baseline_mock.*`) | **9/10 (90%)** | ❌ TC10 fails | n/a | 0/3 |
| Final, M4 code, mock LLM (`eval/results_final_mock.*`) | **10/10 (100%)** | ✅ all pass | n/a | 3/3 |
| Final, M4 code, live gpt-oss + critic (`eval/results_final.*`) | [TODO] | [TODO] | [TODO] | [TODO] |

**Overall pass rate:** 10/10 (100%) in mock mode; [TODO: live result]. Mock mode verifies the pipeline, watcher logic and guardrails with a deterministic stand-in model; only the live run grades digest wording.

### 1.3 Failure analysis

| Case | Run | What failed | Root cause | Category | Fix |
|---|---|---|---|---|---|
| TC10 | baseline | Model emitted `SET_PREF=every_minute` and it was saved to memory | `handle_user_chat` wrote any `SET_PREF` value; the MCP tool had the same gap | Other: missing output/memory guardrail | Allow-list `all`, `concise`, `urgent_only` in both places |
| S01 | baseline | "When is my stock market analysis project due?" was refused | Pre-LLM regex blocked topic words that also appear in real course titles | Other: input guardrail false positive | Removed the topic words; injection/trivia patterns kept |
| S02 | baseline | Empty model output produced an empty alert | No fallback in `process_handoff` | Reasoning / output handling | Template digest built from the payload |
| S03 | baseline | An invented date ("Jan 01") reached the student | Nothing checked the digest against the payload | Reasoning (hallucination) | Date-grounding guardrail + template fallback |
| User testing | live app | 3/5 testers saw wrong due times | Times converted to the server's timezone (UTC on the cloud host), 5 h ahead of Eastern | Other: data formatting bug | Convert to `America/New_York`; regression test |
| [TODO live failures] | final (live) | | | prompt / retrieval / reasoning / other | |

### 1.4 Agent improvements
See the README section **CHANGES (M3 → M4)**: 8 changes, each with its reason and measured impact. Unit tests went from 14 to 22, all passing.

---

## Part 2: User Testing Report

### 2.1 Session summaries
Five external testers (FGCU undergraduates, none on the team or in our section) connected Clockwise to their own Canvas accounts. Full summaries in `docs/M4/user_testing_sessions.md` (Appendix A).

| # | Tester | Format | Outcome | Rating (1–5) |
|---|---|---|---|---|
| 1 | Sophomore, Entrepreneurship | Live | Setup easy; correct "next assignment" answer | 4 |
| 2 | Senior, Entrepreneurship | Live | Setup slow but fine; got a time-blocked plan; wrong due times | 4 |
| 3 | Senior, Software Engineering | Live | Setup easy; good priority ranking; wrong due day | 4 |
| 4 | Senior, Software Engineering | Live | Planning question refused; thought app froze while loading | 4 |
| 5 | Sophomore, Entrepreneurship | Live | ≈4 min to connect, ≈2 min per answer; wrong due time; would not use | 3 |
| | | | | **mean 3.8; 80% ≥4** |

**Against the M3 success criteria:**
- ≥80% complete all tasks with ≤1 hint: **not measurable as planned.** Sessions were open-ended; 5/5 completed setup and got an answer to their own question with no hints, but scripted tasks (b) and (d) were not run.
- Q1 / Q2 means ≥4.0: **not collected.** One overall rating per tester was collected instead (mean 3.8, below 4.0).
- ≥60% rate likelihood to keep using at 4+: **not directly collected.** 4/5 (80%) said they would use it; 4/5 gave an overall 4.
- No date misread: **failed.** No tester misread a correct date, but the app displayed wrong times to 3 testers (bug, now fixed). This is a rebuild trigger in our M3 plan, and we treated it as one.

### 2.2 Synthesis

**Patterns.** Three patterns held across three or more testers. First, testers want Clockwise to plan, not just remind. Four of five asked for some form of planning: a calendar view that works "like your personal school advisor" (tester 1), time blocks for the whole schedule (tester 2), a ranked list of the week's assignments (tester 3), and estimates of how long each assignment will take so they can order their work, exported to Outlook (tester 4). Nobody asked for more alerts. Second, testers trusted the simple interface. Four described it as simple, "basic and straight to the point," "super simple," or "very straightforward," and tester 3 said he dislikes interfaces with "so much stuff." Third, accuracy and speed broke trust. Three testers saw wrong due times, and three described slowness: setup "took a little long" (tester 2), the dimmed loading screen looked broken (tester 4), and connecting took about four minutes with two minutes per answer (tester 5).

**Strongest validation evidence.** Tester 1, without being asked about business models, said: "You could probably get the school to, like, start making it a thing." That supports the M3 conclusion that a campus license, not student subscriptions, is the viable path. Tester 3's session is the strongest product evidence: when asked to rank his week, Clockwise ordered his real assignments and he reacted positively.

**Most important failure.** The date bug. Our core value proposition is "know exactly when things are due," and three of five testers saw times that were wrong; one saw a Wednesday deadline shown as Thursday. Tester 3 guessed the agent was reading Canvas's "available until" date. The real cause was simpler: times were converted to the server's timezone, which is UTC on the cloud host, five hours ahead of Fort Myers. Our evaluation suite could not catch it because the expected values were produced by the same formatter. This changed our thinking in two ways. The evaluation needs at least one end-to-end check against a known real-world time, not just internal consistency. And a single accuracy error costs more trust than any feature earns: tester 5's "Probably not, to be honest" followed directly from a wrong time plus slow answers.

A second, quieter failure: push notifications, a core M3 feature, had weak pull. Two testers already get Canvas notifications and would not install a third-party app unless alerts were customizable and different from Canvas's own.

**Top three changes before the final pitch.**
1. **Accuracy first (done in M4).** Due times now use Eastern time, with a regression test built from the testers' cases, plus the date-grounding guardrail. Chosen first because it breaks the core promise.
2. **Speed and visible progress.** Cut cloud-database round trips (every memory read currently re-runs table setup over HTTP), and replace the dimmed screen with an animated "checking Canvas…" state. Chosen because three testers flagged it, and it is the one complaint from the tester who would not use Clockwise.
3. **A planning answer.** Let the agent rank the week's work by due date and points, answer "how long might this take" instead of refusing it, and export a chosen work time as a calendar event. Chosen because four of five testers asked for it unprompted, and it differentiates Clockwise from Canvas's own notifications.

**Limitations.** Testers were seniors and sophomores from two majors (Entrepreneurship and Software Engineering), sessions were short and open-ended, and one overall rating replaced the planned Q1–Q3.

---

## Part 3: Pivot or Proceed

### 3.1 Decision: Proceed, with the product refocused from alerts to planning

**Decision: Proceed.** The core agent works and testers want it, but the evidence shifts which half of Clockwise matters most.

**Evidence from evaluation.** After the M4 changes the agent meets the threshold we committed to in M3: 10/10 core cases, all critical cases passing, and 3/3 supplementary cases for the failure modes we had named (wrongful refusals, empty output, hallucinated dates). Before the fixes, an invalid preference could be written to memory and a hallucinated date could reach a student. Both are now blocked by output guardrails, and the unit suite grew from 14 to 22 tests. The pipeline is sound enough to build on, so a pivot away from the two-agent design is not warranted. [TODO: confirm with the live critic run.]

**Evidence from user testing.** All five testers completed setup and got useful answers from their own live Canvas data, and four of five rated Clockwise 4/5. That is real validation for a beta. But what they valued was not the deadline-change alert we designed around. Four of five asked for planning help: a calendar, time blocks, ranking, or time estimates. Two said they would not install a separate app for notifications they already get from Canvas. The one tester who would not use Clockwise cited speed and a wrong time, both fixable, not the concept.

**Why not pivot.** The data layer testers need for planning (every assignment, due date, points and submission state) is exactly what the WatcherAgent already maintains. Planning is an extension of the same agents, not a new product. Tester 1's suggestion that the school adopt it also matches our M3 business finding that a campus license is the only model that breaks even.

**What changes.** We keep the WatcherAgent and its silent-unless-changed alerts, but they become secondary. The ChatAgent's scope expands from "deadlines and notification settings" to "deadlines and planning your coursework," so time-estimate and prioritization questions stop being refused. Before the final pitch we will ship accurate times (done), faster responses with a visible loading state, and a ranked weekly plan with calendar export. Success for the next round: mean rating ≥4.0, zero wrong dates, and a majority of testers using the plan feature unprompted.

### 3.2 Updated BMC
See `docs/M4/bmc_updated.md`. Changed blocks: Customer Segments, Value Propositions, Channels, Customer Relationships, Revenue Streams, Key Activities.

---

## Appendix A: Session summaries
See `docs/M4/user_testing_sessions.md`.

## Appendix B: Reproduce
```
pip install -r requirements.txt
python -m pytest                              # 22 tests
python -m src.evaluate --label final_mock     # mock
python -m src.evaluate --live --label final   # live + critic
```
