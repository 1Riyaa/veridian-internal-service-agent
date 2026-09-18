import streamlit as st
from agent import InternalServiceAgent
from data import EMPLOYEE_REQUESTS, TICKETS, POLICIES

st.set_page_config(page_title="Veridian Internal Service Agent", page_icon="🛠️", layout="wide")

if "agent" not in st.session_state:
    st.session_state.agent = InternalServiceAgent()
if "messages" not in st.session_state:
    st.session_state.messages = []

if "tickets" not in st.session_state:
    st.session_state.tickets = list(TICKETS)

st.title("🛠️ Veridian Internal Service Agent")
st.caption("Assignment 2 — Internal IT Support | Policy-grounded prototype")

with st.sidebar:
    st.header("Demo Controls")
    st.write("Choose a supplied employee request to demonstrate the agent.")
    choices = {f'{r["id"]} — {r["employee"]}': r for r in EMPLOYEE_REQUESTS}
    selected = st.selectbox("Employee request", ["— Select —"] + list(choices.keys()))
    if selected != "— Select —":
        r = choices[selected]
        if st.button("Load request"):
            st.session_state.demo_text = r["request"]
            st.session_state.demo_employee = r["employee"]
            st.session_state.demo_email = r["email"]
            st.session_state.messages = []
            st.rerun()

    st.divider()
    st.header("What this prototype demonstrates")
    st.markdown("""
    - Policy retrieval
    - Direct resolution
    - Follow-up questions
    - Risk/ambiguity escalation
    - Structured ticket generation
    - Source citation
    - Audit trail
    """)

    st.divider()
    st.caption("Source data: Veridian Corp Assignment 2 Data Pack. No external company policies are used.")

tab_chat, tab_requests, tab_tickets, tab_policies, tab_audit = st.tabs(
    ["💬 Agent", "📥 Employee Requests", "🎫 Ticket Queue", "📚 Knowledge Base", "🧾 Audit Trail"]
)

with tab_chat:
    if "demo_text" in st.session_state and not st.session_state.messages:
        st.info(f'Demo request from {st.session_state.get("demo_employee","Employee")}: {st.session_state.demo_text}')

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m["role"] == "assistant" and "result" in m:
                r = m["result"]
                c1, c2, c3 = st.columns(3)
                c1.metric("Decision", r["decision"])
                c2.metric("Confidence", r["confidence"])
                c3.metric("Source", r["source"])
                with st.expander("Structured ticket"):
                    st.json(r["ticket"])

    default_prompt = st.session_state.get("demo_text", "")
    prompt = st.chat_input("Describe your IT issue…")
    if prompt:
        employee = st.session_state.get("demo_employee", "Demo Employee")
        email = st.session_state.get("demo_email", "employee@veridian-corp.example")
        st.session_state.messages.append({"role": "user", "content": prompt})
        result = st.session_state.agent.analyze(prompt, employee, email)
        answer = result["response"]
        answer += f"\n\n**Source used:** {result['source']}"
        st.session_state.messages.append({"role": "assistant", "content": answer, "result": result})

        if result.get("ticket"):
            ticket = result["ticket"]

            ticket["id"] = f"TK-{1052 + len(st.session_state.tickets) - len(TICKETS)}"
            ticket["employee"] = employee
            ticket["issue"] = prompt

            st.session_state.tickets.append(ticket)

        st.rerun()

with tab_requests:
    st.subheader("Employee Requests — supplied data")
    st.dataframe(EMPLOYEE_REQUESTS, use_container_width=True, hide_index=True)

with tab_tickets:
    st.subheader("Ticket Queue")

    st.dataframe(
        st.session_state.tickets,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "The queue includes the supplied historical tickets and tickets "
        "created during the current agent session."
    )

with tab_policies:
    st.subheader("Knowledge Base / Policies — supplied data")
    for p in POLICIES:
        with st.expander(f'{p["id"]} — {p["title"]}'):
            st.write(p["text"])

with tab_audit:
    st.subheader("Audit Trail")
    if st.session_state.agent.audit_log:
        st.dataframe(st.session_state.agent.audit_log, use_container_width=True, hide_index=True)
    else:
        st.info("No agent actions yet. Submit a request in the Agent tab.")
