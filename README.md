# ⏰ Clockwise — Multi-Agent Canvas Deadline Assistant

Clockwise is a multi-agent academic assistant for FGCU students that monitors Canvas assignments daily, sends push notifications when deadlines change or unsubmitted assignments are due within 3 days or 24 hours, and provides a conversational AI advisor strictly scoped to your coursework.

---

## 🌐 Option 1: Use the Live Cloud App (For Student Testers)

You do not need to install any code to use Clockwise.

### 1. Open the App & Add to Home Screen
1. Open the live app on your phone or browser: **`https://project-clockwise.streamlit.app/`**
2. **Optional (Install as Mobile App):**
   * **iOS (Safari):** Tap the **Share** icon → **Add to Home Screen**.
   * **Android (Chrome):** Tap the **3-dot menu** → **Add to Home screen**.

### 2. First-Time Account Setup (60 Seconds)
1. Select the **✨ First-Time / New Token** tab.
2. Tap the link to open **[FGCU Canvas Settings](https://fgcu.instructure.com/profile/settings)** and log in.
3. Scroll down to **Approved Integrations** and tap **+ New Access Token**.
4. Set the Purpose to `Clockwise`, tap **Generate Token**, and copy the token.
5. Paste the token into Clockwise, choose a **4-Digit PIN**, and tap **Connect Canvas**.

### 3. Returning Log-In & Token Recovery
* **Same Device:** Your browser automatically remembers your session via a secure first-party cookie.
* **New Device / Returning User:** Open the **🔑 Returning User (PIN)** tab and enter your **Canvas Display Name** (e.g., `John Doe`) + your **4-Digit PIN**.
* **Lost or Expired Token:** Generate a new token in Canvas and submit it on the **First-Time / New Token** tab—Clockwise links accounts by your permanent Canvas ID, so your assignment history and preferences stay intact.

### 4. Enable Lock-Screen Push Notifications
1. Once logged in, expand **🔔 Push Notifications, Schedule & Account** at the top of the app to view your personal push topic (e.g., `clockwise_fgcu_a1b2c3d4`).
2. Install the free **ntfy** app ([iOS App Store](https://apps.apple.com/us/app/ntfy/id1625396347) / [Google Play](https://play.google.com/store/apps/details?id=io.heckel.ntfy)).
3. Tap **`+`** in the ntfy app and subscribe to your personal topic name.

---

## 💻 Option 2: Run Locally on Your Machine (For Developers & Grading)

### 1. Clone & Install Dependencies

```bash
git clone <YOUR_REPO_URL>
cd clockwise
python -m venv .venv

# Windows (Git Bash)
source .venv/Scripts/activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment Variables (`.env`)
Create a `.env` file in the project root directory:

```env
# Required for AI Chat & Triage Digest
NRP_BASE_URL=[https://ellm.nrp-nautilus.io/v1](https://ellm.nrp-nautilus.io/v1)
NRP_API_KEY=your_nrp_api_key_here
NRP_MODEL=gpt-oss

# Optional: For CLI / Local Canvas Polling
CANVAS_BASE_URL=[https://fgcu.instructure.com](https://fgcu.instructure.com)
CANVAS_TOKEN=your_canvas_access_token_here

# Optional: Leave blank to use local SQLite (clockwise.db), or set for Turso Cloud DB
TURSO_DATABASE_URL=
TURSO_AUTH_TOKEN=
```

*(Note: If `TURSO_DATABASE_URL` is left blank, Clockwise automatically creates and uses a local `clockwise.db` SQLite file).*

### 3. Launch the Web App Locally

```bash
streamlit run src/app.py
```

Open **`http://localhost:8501`** in your browser.

### 4. Run Automated Tests & Daily Watcher CLI

```bash
# Run the test suite (uses isolated local SQLite + offline fixtures)
python -m pytest

# Poll Canvas for all registered users from the command line
python -m src.watcher --all-users
```

---

## 🏗️ System Architecture

* **Agent 1 — Backend Watcher (`src/watcher.py`):** Polls the Canvas REST API, diffs assignments against `assignments_snapshot`, and enqueues a `HandoffPayload` into `handoff_queue` only when `NEW`, `DUE_DATE_MOVED`, `REMINDER_3_DAY` (within 72h unsubmitted), or `REMINDER_1_DAY` (within 24h unsubmitted) triggers occur.
* **Agent 2 — Frontend Chat & Advisor (`src/chat_agent.py`):** Consumes handoffs using a ReAct loop (`THOUGHT` / `ACTION_MEMORY` / `ANSWER`), sends push notifications via `ntfy.sh`, updates persistent notification preferences (`concise`, `all`, `urgent_only`), and enforces dual-layer input/system guardrails.
* **Persistent Memory Layer (`src/state.py` & `src/mcp_server.py`):** Multi-tenant SQLite / Turso state storing assignment baselines, user preferences, and MCP tool bindings.

---

## 🔁 CHANGES (M3 → M4)

All changes below were made after M3 (Oct 28) and are in this repo's commit history. Eval numbers are from `python -m src.evaluate` (mock LLM, which checks the watcher, guardrails and fallbacks, not digest wording). Baseline = M3/M4-beta code before the fixes (`eval/results_baseline_mock.*`); final = current code (`eval/results_final_mock.*`).

| # | Change | Why | Measured impact |
|---|---|---|---|
| 1 | **Evaluation runner + critic agent** (`src/evaluate.py`, `src/critic.py`, `tests/eval_cases.json`) | The M3 report described an eval suite and critic that were not in the repo. M4 builds them: the 10 committed cases + 3 supplementary cases for M3's named failure modes (wrongful refusal, empty output, hallucinated date). | Enables measurement. Baseline: **9/10 core (TC10 fails), 0/3 supplementary.** |
| 2 | **Preference allow-list** (`ALLOWED_PREFS` in `chat_agent.py` and the MCP tool) | TC10: the model emitted `SET_PREF=every_minute` and it was written to memory. | TC10 FAIL → PASS. Core **9/10 → 10/10**; all critical cases pass. |
| 3 | **Removed topic words from the pre-LLM regex** (`bitcoin`, `stock market`) | They appear in real course titles ("stock market analysis project") and caused wrongful refusals. Injection/trivia patterns kept; the system prompt still refuses off-topic chat. | S01 FAIL → PASS. |
| 4 | **Template-digest fallback** for empty output or a failed LLM call | An empty model answer produced an empty push alert. | S02 FAIL → PASS. New unit tests for empty output and LLM exceptions. |
| 5 | **Date-grounding output guardrail** (`dates_grounded`) | Nothing checked digest dates against Canvas; an invented date could reach a student. | S03 FAIL → PASS. |
| 6 | **Due times shown in FGCU time** (`STUDENT_TZ` in `src/report.py`, `tzdata` dependency) | 3 of 5 user testers saw wrong due times (e.g. 7:45 shown for a 2:45 deadline; a Wednesday deadline shown as Thursday). Root cause: times were converted to the cloud server's zone (UTC), 5 hours ahead of Eastern. | Regression test reproduces both tester cases and passes. Not covered by the 10 eval cases (they compare the digest against the same formatter), so impact is measured by the unit test and by user testing. |
| 7 | **Chat error fallback fixed** (`src/app.py`) | On an LLM error the app referenced an undefined variable and crashed instead of showing the fallback message. | Manual check; app compiles and shows the fallback text. |
| 8 | **Scheduled Canvas poll fixed** (`.github/workflows/daily_poll.yml`) | Poll steps were gated on a `0 12 * * *` schedule that did not exist, so scheduled polls never ran; only manual runs did. Added that schedule and fixed a shell syntax error in the keep-awake ping. | Operational fix; push alerts can now fire without a manual run. |

**Totals:** unit tests 14 → 22 (all pass). Mock eval core 9/10 → **10/10**, supplementary 0/3 → **3/3**, meets the M3 threshold.

**Live run (real gpt-oss + critic, `eval/results_final.*`):** 8/10 core, all critical cases pass, 3/3 supplementary, critic mean 3.8. TC03 (3.8) and TC04 (3.6) miss the 4.0 critic bar because the digest prompt drops due times and shortens course names; the live run does not yet meet the M3 threshold.

**Run the evaluation:**
```bash
python -m pytest                                  # 22 tests
python -m src.evaluate --label final_mock         # mock LLM
python -m src.evaluate --live --label final       # real NRP model + critic (needs NRP_API_KEY)
```

**Known limitations added in M4:** mock mode cannot grade digest wording (only `--live` + critic does); the date guardrail checks month/day only, not times; the LLM guardrail is inconsistent on planning questions (one tester's time-estimate question was refused while another's time-management question was answered).
