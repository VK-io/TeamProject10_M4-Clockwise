import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from src.watcher import run_watcher
from src.chat_agent import process_handoff, handle_user_chat
from src.state import (
    register_user, get_user, consume_handoffs,
    get_memory, set_memory, DB_PATH
)

st.set_page_config(page_title="Clockwise", page_icon="⏰", layout="centered", initial_sidebar_state="collapsed")

# Minimal mobile-friendly styling
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 1.5rem; padding-bottom: 4rem; max-width: 620px;}
</style>
""", unsafe_allow_html=True)

st.title("⏰ Clockwise")

# Check if user is already logged in via URL param (?uid=...) or session
uid_param = st.query_params.get("uid")
if "user" not in st.session_state:
    st.session_state.user = get_user(uid_param, db_path=DB_PATH) if uid_param else None

# --- SCREEN 1: GUIDED ONBOARDING FOR NEW USERS ---
if not st.session_state.user:
    st.subheader("Connect your FGCU Canvas in 60 seconds")
    st.markdown("""
    1. **[Tap here to open FGCU Canvas Settings](https://fgcu.instructure.com/profile/settings)** and log in.
    2. Scroll down to **Approved Integrations** and tap **+ New Access Token**.
    3. Type `Clockwise` for the purpose, tap **Generate Token**, and paste it below:
    """)

    token_input = st.text_input("Canvas Access Token", type="password", placeholder="Paste your token here...")
    if st.button("Connect Canvas", type="primary", use_container_width=True) and token_input:
        with st.spinner("Verifying your Canvas courses and saving baseline..."):
            try:
                user = register_user(token_input, db_path=DB_PATH)
                run_watcher(user_id=user["user_id"], canvas_token=user["canvas_token"], db_path=DB_PATH)
                st.session_state.user = get_user(user["user_id"], db_path=DB_PATH)
                st.query_params["uid"] = user["user_id"]
                st.rerun()
            except Exception as e:
                st.error("Could not connect to Canvas. Please double-check your token and internet connection.")
    st.stop()

# --- SCREEN 2: MINIMAL CHAT & NOTIFICATION INTERFACE ---
user = st.session_state.user
user_id = user["user_id"]

# Status bar & collapsible settings
col1, col2 = st.columns([3, 1])
with col1:
    sync_status = user.get("last_sync_status") or "ok"
    if str(sync_status).startswith("error"):
        st.caption("⚠️ Last daily Canvas sync encountered a connection issue — will retry automatically.")
    else:
        st.caption(f"✅ Connected • Push topic: `{user['ntfy_topic']}`")
with col2:
    if st.button("🔄 Refresh", use_container_width=True):
        with st.spinner("Checking Canvas..."):
            try:
                res = run_watcher(user_id=user_id, canvas_token=user["canvas_token"], db_path=DB_PATH)
                if res["status"] == "no_material_changes":
                    st.toast("Up to date! No new changes.", icon="✅")
            except Exception:
                st.toast("Connection error while checking Canvas.", icon="⚠️")

with st.expander("🔔 Push Notifications & Schedule"):
    st.markdown(f"**Phone Alerts:** Install the free **ntfy** app and subscribe to `{user['ntfy_topic']}`.")
    pref = get_memory("triage_preference", default="concise", db_path=DB_PATH, user_id=user_id)
    new_pref = st.segmented_control("Alert Style", options=["concise", "all", "urgent_only"], default=pref)
    if new_pref and new_pref != pref:
        set_memory("triage_preference", new_pref, db_path=DB_PATH, user_id=user_id)
        st.rerun()
    st.text(get_memory("latest_report", default="No upcoming assignments.", db_path=DB_PATH, user_id=user_id))

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! I'm monitoring your Canvas deadlines daily. Ask me what's due soon or how to adjust your alerts."}
    ]

# Consume any unread notifications from Watcher Agent
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