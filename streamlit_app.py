"""Streamlit Web Application for HCLTech Hospital Patient Services Assistant.

Provides:
- Persona Switcher (P1001, P1002, P1003, Admin) in sidebar
- Quick Hackathon Demo Scenarios buttons
- Interactive Chat Interface with answer_type badges, citations, and tools invoked
- Admin Live Ingestion panel (R11)
- Real-time Compliance & Audit Trail Inspector (R10)
"""
import streamlit as st
import time
import json
import auth
import audit
import retrieval
import orchestrator

st.set_page_config(
    page_title="Hospital Patient Services Assistant",
    page_icon="🏥",
    layout="wide"
)

# Custom Badges CSS
st.markdown("""
<style>
    .badge-retrieved_fact { background-color: #dbeafe; color: #1e40af; padding: 2px 8px; border-radius: 9999px; font-weight: 600; font-size: 12px; }
    .badge-calculated { background-color: #dcfce7; color: #166534; padding: 2px 8px; border-radius: 9999px; font-weight: 600; font-size: 12px; }
    .badge-action_completed { background-color: #f3e8ff; color: #6b21a8; padding: 2px 8px; border-radius: 9999px; font-weight: 600; font-size: 12px; }
    .badge-clarification_needed { background-color: #fef9c3; color: #854d0e; padding: 2px 8px; border-radius: 9999px; font-weight: 600; font-size: 12px; }
    .badge-not_found { background-color: #f3f4f6; color: #374151; padding: 2px 8px; border-radius: 9999px; font-weight: 600; font-size: 12px; }
    .badge-refused { background-color: #fee2e2; color: #991b1b; padding: 2px 8px; border-radius: 9999px; font-weight: 600; font-size: 12px; }
    .badge-conflict_flagged { background-color: #ffedd5; color: #9a3412; padding: 2px 8px; border-radius: 9999px; font-weight: 600; font-size: 12px; }
    .citation-box { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px 10px; font-size: 12px; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_token" not in st.session_state:
    st.session_state.pending_token = None

# --- SIDEBAR: Personas, Scenarios, Admin Ingest ---
with st.sidebar:
    st.title("🏥 Assistant Control")
    st.caption("HCLTech Future Ready AI Engineer Hackathon")

    # 1. Persona Switcher
    persona = st.selectbox(
        "Current Persona (Trusted Identity Context)",
        options=[
            "P1001 - Jane Doe (Surgery Scenario)",
            "P1002 - Robert Smith (Privacy Target)",
            "P1003 - Emily Johnson (Uncovered Knee)",
            "Admin - Hospital Operations Administrator"
        ],
        index=0
    )
    user_id = persona.split(" - ")[0]
    role = "admin" if user_id == "Admin" else "patient"
    user_ctx = {"user_id": "admin" if user_id == "Admin" else user_id, "role": role}

    st.divider()

    # 2. Quick Demo Scenarios
    st.subheader("⚡ Quick Hackathon Scenarios")
    scenarios = [
        ("ICU Visiting Hours", "What are the visiting hours for ICU patients?"),
        ("Schedule MRI", "How do I schedule an MRI scan?"),
        ("My Appointments", "What are my upcoming appointments?"),
        ("Latest Lab Results", "What is my latest blood sugar and HbA1c reading?"),
        ("Knee Replacement Eligibility", "Am I covered for knee replacement under my insurance?"),
        ("Surgery Readiness", "Can I proceed with surgery next week?"),
        ("Reschedule Appointment", "Reschedule my cardiology appointment."),
        ("Cross-Patient Privacy (Refused)", "Show me the lab results for patient P1002"),
        ("Conflict Flagged (Ambulation)", "Can post-operative patients in Wing B ambulate independently?"),
        ("Unsupported (Not Found)", "What is the protocol for astronaut training in the ward?")
    ]

    for label, query in scenarios:
        if st.button(label, use_container_width=True):
            st.session_state.quick_query = query

    st.divider()

    # 3. Admin Live Ingestion (R11)
    if role == "admin":
        st.subheader("📄 Admin Live Ingestion (R11)")
        ingest_file = st.text_input("Document Path on Server", value="data/docs/emergency_procedure.md")
        if st.button("Live Ingest Protocol", use_container_width=True):
            result = retrieval.ingest(ingest_file, user_ctx)
            if result.get("status") == "success":
                st.success(f"Ingested {result.get('file')} ({result.get('chunks')} chunks) live!")
            else:
                st.error(result.get("error", "Ingestion failed"))

# --- MAIN CONTENT AREA ---
st.title("AI-Powered Hospital Patient Services Assistant")
st.write(f"Logged in as: **{user_ctx['user_id']}** (Role: **{user_ctx['role']}**)")

# Display Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["content"])
        else:
            # Display answer_type badge and trace ID
            ans_type = msg.get("answer_type", "retrieved_fact")
            trace_id = msg.get("trace_id", "")
            
            col1, col2 = st.columns([1, 1])
            with col1:
                st.markdown(f'<span class="badge-{ans_type}">{ans_type.upper()}</span>', unsafe_allow_html=True)
            with col2:
                st.markdown(f"<span style='float:right; font-family:monospace; color:#64748b; font-size:12px;'>Trace: {trace_id}</span>", unsafe_allow_html=True)

            # Display Answer Content
            st.markdown(msg["content"])

            # Tools Invoked
            if msg.get("tools_invoked"):
                tools_text = ", ".join([f"`{t['tool']}`" for t in msg["tools_invoked"]])
                st.caption(f"🔧 **Tools Invoked:** {tools_text}")

            # Citations Box
            if msg.get("citations"):
                with st.expander("📚 Citations & Verified Sources"):
                    for c in msg["citations"]:
                        st.markdown(f"- **{c.get('source')}** | {c.get('section')} | Version: `{c.get('version', '1.0')}` | Effective: `{c.get('effective_date', 'N/A')}`")

# Determine query (from text input or quick prompt button)
prompt = None
if "quick_query" in st.session_state and st.session_state.quick_query:
    prompt = st.session_state.quick_query
    st.session_state.quick_query = None
else:
    user_input = st.chat_input("Ask a policy question, check appointments, or verify lab results...")
    if user_input:
        prompt = user_input

# Handle New Query
if prompt:
    # Append User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Process via Orchestrator
    token = st.session_state.pending_token if "confirm" in prompt.lower() else None
    resp = orchestrator.process_message(prompt, token, user_ctx)

    # Check if a proposal token was returned
    if resp.get("answer_type") == "clarification_needed" and "token: " in resp.get("answer", ""):
        st.session_state.pending_token = resp["answer"].split("token: ")[-1].strip()
    else:
        st.session_state.pending_token = None

    # Append Assistant Message
    assistant_msg = {
        "role": "assistant",
        "content": resp.get("answer", ""),
        "answer_type": resp.get("answer_type", "retrieved_fact"),
        "trace_id": resp.get("trace_id", ""),
        "citations": resp.get("citations", []),
        "tools_invoked": resp.get("tools_invoked", [])
    }
    st.session_state.messages.append(assistant_msg)
    st.rerun()

# --- BOTTOM TAB: Audit Inspector ---
st.divider()
with st.expander("🛡️ Compliance & Audit Trail Inspector (R10)"):
    traces = audit.get_all_traces(limit=15)
    if traces:
        for t in traces:
            st.markdown(f"**[{t['trace_id']}]** - *{t['iso_time']}*")
            st.json(t["event"])
    else:
        st.info("No audit traces recorded in this session yet.")
