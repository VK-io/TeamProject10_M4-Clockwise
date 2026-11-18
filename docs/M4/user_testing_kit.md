# Clockwise: M4 User Testing Kit

This kit follows the plan we committed to in M3 (Section 8). Use it for every session so the five summaries can be compared.

## Before each session
- [ ] Tester is an FGCU undergrad, **not** on the team or in our CEN 4930 section. Write down their major and year, and whether they have missed a deadline because of a schedule change.
- [ ] `.env` has a working `NRP_API_KEY`. Delete `clockwise.db` so the tester starts fresh.
- [ ] Run `streamlit run src/app.py` and have `tests/fixtures/assignments.json` open in an editor so you can move a deadline.
- [ ] Turn on the AI notetaker. Get spoken consent on the recording: *"Is it OK if I record this to take notes? It's only for our class project, and we won't use your name."*

## Script (~20 min)
1. **Intro (2 min).** "Clockwise watches Canvas and tells you when a deadline moves. Please think out loud. We're testing the agent, not you."
2. **Task (10 min).** Record each step on the tracking sheet below.
   - **a.** "Click poll to set up Clockwise." (baseline)
   - **b.** *Facilitator moves a deadline in the fixture file and polls again.* "Something changed. Tell me what changed and when it's due now."
   - **c.** "Ask Clockwise what you have due in the next week."
   - **d.** "Make Clockwise only alert you about urgent things, by chatting with it."
   - *(Optional)* "Ask it anything you'd want to know about your classes." This probes for wrongful refusals.
3. **Questionnaire (5 min).** Read each question aloud so the answer ends up in the transcript.
4. **Debrief (3 min).** "What would you change first?"

## Questionnaire
**Quantitative (1–5):**
- Q1. How easy was it to understand what deadline changed? (1 = very hard, 5 = very easy)
- Q2. How much would you trust Clockwise to tell you about a moved deadline? (1 = not at all, 5 = completely)
- Q3. How likely are you to keep Clockwise running this semester? (1 = not at all, 5 = definitely)

**Qualitative:**
- O1. Describe in your own words what the alert told you. Was anything missing or confusing?
- O2. When would a notification from Clockwise be annoying rather than helpful?
- O3. Was there a question you wanted to ask that Clockwise refused or answered badly?
- O4. What would make you recommend this to a friend, or pay for it?

## Tracking sheet (one per session)
| Step | Completed? | Time (s) | Hints | Notes |
|---|---|---|---|---|
| a. Baseline | | | | |
| b. Explain the moved deadline (did they state the new date correctly?) | | | | |
| c. "What's due next week?" | | | | |
| d. Switch to urgent-only | | | | |

Q1 ___  Q2 ___  Q3 ___

## After each session
Export the notetaker transcript and send it to Claude along with the tracking sheet. Claude drafts `docs/M4/sessions/session_N.md` in the template below, using only what's in the transcript. A teammate who was there then checks the draft.

## Session summary template (rubric format)
- **Tester:** role and context, no name (e.g. "Junior, Nursing, heavy Canvas user, has missed a moved quiz")
- **Date and format:** in person / video / async
- **Task given:**
- **What they did:** step by step
- **Where they got stuck:**
- **What surprised us:**
- **Would they use it again? What would make them more likely to?**
- **Scores:** Q1 / Q2 / Q3; steps completed; hints used

## M3 success criteria (checked in the synthesis)
- At least 80% of testers complete all 4 sub-tasks with no more than 1 hint
- Mean Q1 ≥ 4.0 and mean Q2 ≥ 4.0
- At least 60% rate Q3 at 4 or 5
- No tester misstates the moved deadline

**Rebuild triggers:** any tester misreads a date · 2 or more wrongful refusals · mean Q2 < 3.0 · most testers call the alerts noise
