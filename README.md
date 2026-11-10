# Clockwise — Canvas Deadline Change Agent

## 1. Problem Addressed
Clockwise prevents students from missing coursework caused by post-syllabus schedule shifts by monitoring Canvas course feeds and surfacing assignment changes rather than static task snapshots.

## 2. Current Capabilities
- **Multi-Agent Architecture:** Splits execution between a backend `WatcherAgent` (`src/watcher.py`) that polls Canvas and diffs snapshots, and a frontend `ChatAgent` (`src/chat_agent.py`) that triages handoffs and answers student queries.
- **Explicit Handoff:** `WatcherAgent` serializes a structured `HandoffPayload` into SQLite (`handoff_queue`) consumed by `ChatAgent` only when `NEW` or `DUE_DATE_MOVED` events occur.
- **Reasoning Pattern (ReAct):** `ChatAgent` executes a structured `THOUGHT` -> `ACTION_MEMORY` -> `ANSWER` reasoning trace before composing digests or updating settings.
- **Persistent Memory Layer:** Stores student notification preferences (`concise`, `all`, `urgent_only`), latest digests, and 14-day schedules in SQLite (`user_memory`).
- **Role Guardrails:** Enforces pre-LLM regex filtering and strict system prompt boundaries so the agent refuses off-topic queries outside of Canvas coursework.
- **Localhost Web UI & Push Alerts:** Provides a Streamlit chatbox interface (`src/app.py`) with toast alerts and optional `ntfy.sh` mobile push notifications.

## 3. CHANGES (M2 → M3)
- Refactored monolithic `src/agent.py` into a two-agent architecture (`src/watcher.py` and `src/chat_agent.py`) connected via an explicit `HandoffPayload` queue in `src/state.py`.
- Added a ReAct/Chain-of-Thought reasoning pattern with inspectable reasoning traces in `src/chat_agent.py`.
- Implemented a persistent SQLite memory layer (`user_memory` table) to store user notification thresholds and schedule state across sessions.
- Added dual-layer input/system guardrails restricting the agent strictly to Canvas assignments and deadlines.
- Built a localhost Streamlit web application (`src/app.py`) supporting interactive chat and real-time change notifications.

## 4. Setup and Execution
1. Clone the repository and establish a virtual environment:
   ```bash
   python -m venv venv
   # On macOS/Linux:
   source venv/bin/activate
   # On Windows (Git Bash):
   source venv/Scripts/activate
   pip install -r requirements.txt
   ```
2. Execute locally:
    ```bash
    # Launch the Streamlit Localhost Web App (Chatbox + Notifications)
    streamlit run src/app.py

    # CLI Mode (Offline using /tests/fixtures or Live via Canvas API)
    python -m src.agent --offline
    python -m src.agent

    # Run Automated Test Suite
    python -m pytest
    ```
## 5. Known Limitations
- Assignments lacking an explicit due_at timestamp are bypassed during timeline diff calculations.
- Self-service Canvas API token creation depends on institution-level policy and cannot be generated programmatically if disabled by FGCU.
- Rapid assignment metadata updates that occur between polling cycles only capture the net difference between snapshots, omitting intermediate changes.
