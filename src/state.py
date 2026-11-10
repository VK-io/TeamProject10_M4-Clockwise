import os
import sqlite3
import json
import hashlib
import requests
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv
from src.report import parse_due

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

DB_PATH = "clockwise.db"


def _get_secret(key: str, default: str = None) -> str:
    val = os.getenv(key)
    if val:
        return val
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return default


def _use_turso(db_path: str) -> bool:
    return (
        db_path == DB_PATH
        and bool(_get_secret("TURSO_DATABASE_URL"))
        and bool(_get_secret("TURSO_AUTH_TOKEN"))
    )


def _exec(sql: str, params: Tuple = (), db_path: str = DB_PATH) -> List[Tuple]:
    """Executes SQL against Turso HTTP API in cloud mode or local SQLite in local/test mode."""
    if _use_turso(db_path):
        raw_url = _get_secret("TURSO_DATABASE_URL")
        token = _get_secret("TURSO_AUTH_TOKEN")
        url = raw_url.replace("libsql://", "https://").rstrip("/") + "/v2/pipeline"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        args = []
        for p in params:
            if p is None:
                args.append({"type": "null"})
            elif isinstance(p, int):
                args.append({"type": "integer", "value": str(p)})
            else:
                args.append({"type": "text", "value": str(p)})

        payload = {"requests": [{"type": "execute", "stmt": {"sql": sql, "args": args}}, {"type": "close"}]}
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        res = resp.json()["results"][0]
        if res["type"] == "error":
            raise RuntimeError(res["error"]["message"])
        rows = res["response"]["result"].get("rows", [])
        return [
            tuple(None if c["type"] == "null" else (int(c["value"]) if c["type"] == "integer" else c["value"]) for c in r)
            for r in rows
        ]
    else:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            rows = cur.fetchall()
            conn.commit()
            return rows


def init_db(db_path: str = DB_PATH):
    _exec("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            display_name TEXT,
            canvas_token TEXT NOT NULL,
            pin_hash TEXT,
            session_secret TEXT,
            ntfy_topic TEXT NOT NULL,
            last_sync_at TEXT,
            last_sync_status TEXT
        )
    """, db_path=db_path)
    # Safe column migration if the table was already created in Step 2
    for col in ("display_name TEXT", "pin_hash TEXT", "session_secret TEXT"):
        try:
            _exec(f"ALTER TABLE users ADD COLUMN {col}", db_path=db_path)
        except Exception:
            pass

    _exec("""
        CREATE TABLE IF NOT EXISTS assignments_snapshot (
            user_id TEXT NOT NULL DEFAULT 'default',
            id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            due_at TEXT,
            updated_at TEXT,
            reminded_3d INTEGER DEFAULT 0,
            reminded_1d INTEGER DEFAULT 0,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            PRIMARY KEY (user_id, id)
        )
    """, db_path=db_path)
    _exec("""
        CREATE TABLE IF NOT EXISTS user_memory (
            user_id TEXT NOT NULL DEFAULT 'default',
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, key)
        )
    """, db_path=db_path)
    _exec("""
        CREATE TABLE IF NOT EXISTS handoff_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL DEFAULT 'default',
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            consumed INTEGER DEFAULT 0
        )
    """, db_path=db_path)


def _hash(val: str) -> str:
    return hashlib.sha256(val.strip().encode("utf-8")).hexdigest()


def register_user(
    canvas_token: str,
    pin: str = "0000",
    canvas_uid: Optional[str] = None,
    display_name: str = "Student",
    db_path: str = DB_PATH
) -> Dict[str, str]:
    """
    Registers or updates a student profile keyed by their permanent Canvas numeric ID.
    Generating a new token reconnects to the same user_id and assignment history.
    """
    init_db(db_path)
    clean_token = canvas_token.strip()
    user_id = f"canvas_{canvas_uid}" if canvas_uid else _hash(clean_token)[:12]
    pin_hash = _hash(pin)
    session_secret = _hash(f"{user_id}:{pin_hash}:{clean_token[:6]}")[:32]
    ntfy_topic = f"clockwise_fgcu_{_hash(user_id)[:8]}"

    _exec("""
        INSERT INTO users (user_id, display_name, canvas_token, pin_hash, session_secret, ntfy_topic, last_sync_status)
        VALUES (?, ?, ?, ?, ?, ?, 'pending')
        ON CONFLICT(user_id) DO UPDATE SET
            display_name = excluded.display_name,
            canvas_token = excluded.canvas_token,
            pin_hash = excluded.pin_hash,
            session_secret = excluded.session_secret
    """, (user_id, display_name.strip(), clean_token, pin_hash, session_secret, ntfy_topic), db_path=db_path)

    return {
        "user_id": user_id,
        "display_name": display_name.strip(),
        "canvas_token": clean_token,
        "session_secret": session_secret,
        "ntfy_topic": ntfy_topic
    }


def _row_to_user(r: Tuple) -> Dict[str, str]:
    return {
        "user_id": r[0],
        "display_name": r[1] or "Student",
        "canvas_token": r[2],
        "session_secret": r[3],
        "ntfy_topic": r[4],
        "last_sync_at": r[5],
        "last_sync_status": r[6]
    }


def get_user(user_id: str, db_path: str = DB_PATH) -> Optional[Dict[str, str]]:
    init_db(db_path)
    rows = _exec(
        "SELECT user_id, display_name, canvas_token, session_secret, ntfy_topic, last_sync_at, last_sync_status FROM users WHERE user_id = ?",
        (user_id,), db_path=db_path
    )
    return _row_to_user(rows[0]) if rows else None


def get_user_by_session(session_secret: str, db_path: str = DB_PATH) -> Optional[Dict[str, str]]:
    """Authenticates a device automatically via its first-party browser cookie."""
    if not session_secret:
        return None
    init_db(db_path)
    rows = _exec(
        "SELECT user_id, display_name, canvas_token, session_secret, ntfy_topic, last_sync_at, last_sync_status FROM users WHERE session_secret = ?",
        (session_secret.strip(),), db_path=db_path
    )
    return _row_to_user(rows[0]) if rows else None


def authenticate_by_pin(display_name: str, pin: str, db_path: str = DB_PATH) -> Optional[Dict[str, str]]:
    """Allows returning users to log in on any device using their Name + 4-digit PIN."""
    init_db(db_path)
    pin_hash = _hash(pin)
    rows = _exec(
        "SELECT user_id, display_name, canvas_token, session_secret, ntfy_topic, last_sync_at, last_sync_status "
        "FROM users WHERE LOWER(display_name) = LOWER(?) AND pin_hash = ?",
        (display_name.strip(), pin_hash), db_path=db_path
    )
    return _row_to_user(rows[0]) if rows else None


def list_all_users(db_path: str = DB_PATH) -> List[Dict[str, str]]:
    init_db(db_path)
    rows = _exec("SELECT user_id, canvas_token, ntfy_topic FROM users", db_path=db_path)
    return [{"user_id": r[0], "canvas_token": r[1], "ntfy_topic": r[2]} for r in rows]


def update_sync_status(user_id: str, status: str, db_path: str = DB_PATH):
    init_db(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    _exec("UPDATE users SET last_sync_at = ?, last_sync_status = ? WHERE user_id = ?", (now_iso, status, user_id), db_path=db_path)


def get_current_snapshot(db_path: str = DB_PATH, user_id: str = "default") -> Dict[int, Dict[str, Any]]:
    init_db(db_path)
    rows = _exec(
        "SELECT id, course_id, name, due_at, updated_at, reminded_3d, reminded_1d FROM assignments_snapshot WHERE user_id = ?",
        (user_id,), db_path=db_path
    )
    return {
        row[0]: {
            "id": row[0],
            "course_id": row[1],
            "name": row[2],
            "due_at": row[3],
            "updated_at": row[4],
            "reminded_3d": int(row[5] or 0),
            "reminded_1d": int(row[6] or 0),
        }
        for row in rows
    }


def compute_diff_and_update(
    current_assignments: List[Dict[str, Any]],
    db_path: str = DB_PATH,
    user_id: str = "default",
    now: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    init_db(db_path)
    previous_snapshot = get_current_snapshot(db_path, user_id=user_id)
    now_dt = now or datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    changes = []

    current_ids = {a["id"] for a in current_assignments}

    for assign in current_assignments:
        a_id = assign["id"]
        due_at = assign.get("due_at")
        updated_at = assign.get("updated_at")
        course_id = assign["course_id"]
        name = assign.get("name", "Untitled")
        submitted = bool(assign.get("submitted", False))
        graded = bool(assign.get("graded", True))

        old = previous_snapshot.get(a_id)
        rem_3d = old["reminded_3d"] if old else 0
        rem_1d = old["reminded_1d"] if old else 0

        if a_id not in previous_snapshot:
            changes.append({
                "event_type": "NEW",
                "assignment_id": a_id,
                "name": name,
                "course_id": course_id,
                "due_at": due_at
            })
        else:
            if (old["due_at"] or "") != (due_at or ""):
                changes.append({
                    "event_type": "DUE_DATE_MOVED",
                    "assignment_id": a_id,
                    "name": name,
                    "course_id": course_id,
                    "old_due_at": old["due_at"],
                    "new_due_at": due_at
                })
                rem_3d, rem_1d = 0, 0

        due_dt = parse_due(due_at)
        if due_dt and graded and not submitted:
            hours_left = (due_dt - now_dt).total_seconds() / 3600.0
            if 0 < hours_left <= 24 and not rem_1d:
                changes.append({
                    "event_type": "REMINDER_1_DAY",
                    "assignment_id": a_id,
                    "name": name,
                    "course_id": course_id,
                    "due_at": due_at
                })
                rem_1d = 1
                rem_3d = 1
            elif 24 < hours_left <= 72 and not rem_3d:
                changes.append({
                    "event_type": "REMINDER_3_DAY",
                    "assignment_id": a_id,
                    "name": name,
                    "course_id": course_id,
                    "due_at": due_at
                })
                rem_3d = 1

        if a_id not in previous_snapshot:
            _exec("""
                INSERT INTO assignments_snapshot
                (user_id, id, course_id, name, due_at, updated_at, reminded_3d, reminded_1d, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, a_id, course_id, name, due_at, updated_at, rem_3d, rem_1d, now_iso, now_iso), db_path=db_path)
        else:
            _exec("""
                UPDATE assignments_snapshot
                SET name = ?, due_at = ?, updated_at = ?, reminded_3d = ?, reminded_1d = ?, last_seen = ?
                WHERE user_id = ? AND id = ?
            """, (name, due_at, updated_at, rem_3d, rem_1d, now_iso, user_id, a_id), db_path=db_path)

    for old_id, old_data in previous_snapshot.items():
        if old_id not in current_ids:
            changes.append({
                "event_type": "REMOVED",
                "assignment_id": old_id,
                "name": old_data["name"],
                "course_id": old_data["course_id"]
            })
            _exec("DELETE FROM assignments_snapshot WHERE user_id = ? AND id = ?", (user_id, old_id), db_path=db_path)

    return changes


def has_snapshot(db_path: str = DB_PATH, user_id: str = "default") -> bool:
    init_db(db_path)
    rows = _exec("SELECT 1 FROM assignments_snapshot WHERE user_id = ? LIMIT 1", (user_id,), db_path=db_path)
    return len(rows) > 0


def set_memory(key: str, value: Any, db_path: str = DB_PATH, user_id: str = "default"):
    init_db(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    val_str = json.dumps(value) if not isinstance(value, str) else value
    _exec("""
        INSERT INTO user_memory (user_id, key, value, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
    """, (user_id, key, val_str, now_iso), db_path=db_path)


def get_memory(key: str, default: Any = None, db_path: str = DB_PATH, user_id: str = "default") -> Any:
    init_db(db_path)
    rows = _exec("SELECT value FROM user_memory WHERE user_id = ? AND key = ?", (user_id, key), db_path=db_path)
    if not rows:
        return default
    try:
        return json.loads(rows[0][0])
    except json.JSONDecodeError:
        return rows[0][0]


def enqueue_handoff(payload: Dict[str, Any], db_path: str = DB_PATH, user_id: str = "default"):
    init_db(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    _exec(
        "INSERT INTO handoff_queue (user_id, payload_json, created_at, consumed) VALUES (?, ?, ?, 0)",
        (user_id, json.dumps(payload), now_iso), db_path=db_path
    )


def consume_handoffs(db_path: str = DB_PATH, user_id: str = "default") -> List[Dict[str, Any]]:
    init_db(db_path)
    rows = _exec(
        "SELECT id, payload_json FROM handoff_queue WHERE user_id = ? AND consumed = 0 ORDER BY id ASC",
        (user_id,), db_path=db_path
    )
    if not rows:
        return []
    for r in rows:
        _exec("UPDATE handoff_queue SET consumed = 1 WHERE id = ?", (r[0],), db_path=db_path)
    return [json.loads(r[1]) for r in rows]