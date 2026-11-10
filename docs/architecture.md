# Clockwise M3 Multi-Agent Architecture

```mermaid
flowchart TD
    subgraph 1. USER INPUT & CANVAS
        A[Canvas REST API / Offline Fixtures]
    end

    subgraph 2. AGENT 1: BACKEND WATCHER
        B[MCP Tool Layer: canvas_mcp]
        C[(SQLite: assignments_snapshot)]
        D[Diff Engine: Emits NEW / DUE_DATE_MOVED]
    end

    subgraph 3. EXPLICIT HANDOFF & MEMORY LAYER
        E[(SQLite: handoff_queue)]
        F[(SQLite: user_memory Preferences & State)]
    end

    subgraph 4. AGENT 2: FRONTEND CHAT & ADVISOR
        G[Input & Role Guardrails]
        H[ReAct Loop: THOUGHT -> ACTION -> ANSWER]
    end

    subgraph 5. OUTPUT & UI
        I[Streamlit Localhost Web App & Push Notification]
        J[Silent Exit: No Material Changes]
    end

    A --> B --> C --> D
    D -->|No Material Change| J
    D -->|HandoffPayload JSON| E
    E --> H
    F <--> H
    G --> H
    H --> I