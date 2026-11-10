import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
import streamlit as st
import streamlit.components.v1 as components
from src.canvas_client import BASE_URL, get_headers
from src.watcher import run_watcher
from src.chat_agent import process_handoff, handle_user_chat
from src.state import (
    register_user, get_user, get_user_by_session,
    authenticate_by_pin, consume_handoffs,
    get_memory, set_memory, DB_PATH
)

st.set_page_config(page_title="Clockwise", page_icon="⏰", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 1.5rem; padding-bottom: 4rem; max-width: 620px;}
</style>
""", unsafe_allow_html=True)


def fetch_user_profile(token: str) -> dict:
    """Fetches the student's permanent Canvas user ID and display name directly."""
    resp = requests.get(f"{BASE_URL}/api/v1/users/self", headers=get_headers(token), timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return {
        "canvas_uid": str(data["id"]),
        "name": data.get("short_name") or data.get("name") or "Student"
    }


def set_browser_cookie(name: str, value: str, days: int = 365):
    """Writes a persistent first-party cookie to the user's mobile or desktop browser."""
    max_age = days * 86400
    components.html(
        f"<script>parent.document.cookie = '{name}={value}; path=/; max-age={max_age}; SameSite=Lax';</script>",
        height=0,
    )


st.title("⏰ Clockwise")

# 1. Check Session State or Browser Cookie (No URL parameters needed)
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None and not st.session_state.get("logged_out"):
    cookie_token = st.context.cookies.get("cw_session")
    if cookie_token:
        st.session_state.user = get_user_by_session(cookie_token, db_path=DB_PATH)

# Write pending cookie if user just logged in
if st.session_state.get("pending_cookie"):
    set_browser_cookie("cw_session", st.session_state.pop("pending_cookie"), days=365)

# --- SCREEN 1: ONBOARDING & RETURNING LOGIN ---
if not st.session_state.user:
    tab_setup, tab_login = st.tabs(["✨ First-Time / New Token", "🔑 Returning User (PIN)"])

    with tab_setup:
        st.markdown("""
        **Connect your FGCU Canvas in 60 seconds:**
        1. **[Tap here to open FGCU Canvas Settings](https://fgcu.instructure.com/profile/settings)** and log in.
        2. Scroll to **Approved Integrations** and tap **+ New Access Token**.
        3. Set Purpose to `Clockwise`, tap **Generate Token**, and paste it below.
        *(Generating a new token later will automatically reconnect to your existing history!)*
        """)
        token_input = st.text_input("Canvas Access Token", type="password", placeholder="Paste your Canvas token...")
        pin_input = st.text_input("Create a 4-Digit PIN (for quick login on other devices)", max_chars=4, type="password", placeholder="e.g. 1234")

        if st.button("Connect Canvas", type="primary", use_container_width=True):
            if not token_input or len(pin_input.strip()) < 4:
                st.warning("Please enter your Canvas token and a 4-digit PIN.")
            else:
                with st.spinner("Verifying your Canvas profile and syncing courses..."):
                    try:
                        profile = fetch_user_profile(token_input.strip())
                        user = register_user(
                            canvas_token=token_input.strip(),
                            pin=pin_input.strip(),
                            canvas_uid=profile["canvas_uid"],
                            display_name=profile["name"],
                            db_path=DB_PATH
                        )
                        run_watcher(user_id=user["user_id"], canvas_token=user["canvas_token"], db_path=DB_PATH)
                        st.session_state.user = get_user(user["user_id"], db_path=DB_PATH)
                        st.session_state.logged_out = False
                        st.session_state.pending_cookie = user["session_secret"]
                        st.rerun()
                    except Exception:
                        st.error("Could not verify token with Canvas. Please check your token and try again.")

    with tab_login:
        st.caption("Already connected before? Enter your Canvas display name and 4-digit PIN.")
        name_login = st.text_input("Your Canvas Name", placeholder="e.g. John Doe")
        pin_login = st.text_input("4-Digit PIN", max_chars=4, type="password")
        if st.button("Log In", type="primary", use_container_width=True):
            found = authenticate_by_pin(name_login, pin_login, db_path=DB_PATH)
            if found:
                st.session_state.user = found
                st.session_state.logged_out = False
                st.session_state.pending_cookie = found["session_secret"]
                st.rerun()
            else:
                st.error("No matching account found. Check your name/PIN or use the 'New Token' tab to reset.")
    st.stop()

# --- SCREEN 2: MINIMAL CHAT & NOTIFICATION INTERFACE ---
user = st.session_state.user
user_id = user["user_id"]
display_name = user.get("display_name") or "Student"

col1, col2 = st.columns([3, 1])
with col1:
    sync_status = user.get("last_sync_status") or "ok"
    if str(sync_status).startswith("error"):
        st.caption("⚠️ Last daily Canvas sync had a connection issue — will retry automatically.")
    else:
        st.caption(f"👋 Hi **{display_name}** • Push topic: `{user['ntfy_topic']}`")
with col2:
    if st.button("🔄 Refresh", use_container_width=True):
        with st.spinner("Checking Canvas..."):
            try:
                res = run_watcher(user_id=user_id, canvas_token=user["canvas_token"], db_path=DB_PATH)
                if res["status"] == "no_material_changes":
                    st.toast("Up to date! No new changes.", icon="✅")
            except Exception:
                st.toast("Connection error while checking Canvas.", icon="⚠️")

with st.expander("🔔 Push Notifications, Schedule & Account"):
    st.markdown(f"**Phone Alerts:** Install the free **ntfy** app and subscribe to `{user['ntfy_topic']}`.")
    pref = get_memory("triage_preference", default="concise", db_path=DB_PATH, user_id=user_id)
    new_pref = st.segmented_control("Alert Style", options=["concise", "all", "urgent_only"], default=pref)
    if new_pref and new_pref != pref:
        set_memory("triage_preference", new_pref, db_path=DB_PATH, user_id=user_id)
        st.rerun()
    st.text(get_memory("latest_report", default="No upcoming assignments.", db_path=DB_PATH, user_id=user_id))
    if st.button("Log out on this device"):
        set_browser_cookie("cw_session", "", days=-1)
        st.session_state.user = None
        st.session_state.logged_out = True
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": f"Hi {display_name}! I'm monitoring your Canvas deadlines daily. Ask me what's due soon or how to adjust your alerts."}
    ]

for handoff in consume_handoffs(db_path=DB_PATH, user_id=user_id):
    res = process_handoff(handoff, db_path=DB_PATH, user_id=user_id, ntfy_topic=user["ntfy_topic"])
    st.session_state.messages.append({
        "role": "assistant",
        "content": f"🔔 **Canvas Update**\n\n{res['digest']}"
    })

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask about your assignments or due dates..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            reply = handle_user_chat(prompt, db_path=DB_PATH, user_id=user_id)
            st.markdown(reply["answer"])
            st.session_state.messages.append({"role": "assistant", "content": reply["answer"]})