import streamlit as st
from agent import InternalServiceAgent
from data import EMPLOYEE_REQUESTS, POLICIES, TICKETS


st.set_page_config(
    page_title="Veridian Internal Service Agent",
    page_icon="🛠️",
    layout="wide",
)


# -----------------------------
# Session State
# -----------------------------

if "agent" not in st.session_state:
    st.session_state.agent = InternalServiceAgent()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "tickets" not in st.session_state:
    # Normalize historical tickets into the same schema
    # used by newly generated tickets.
    st.session_state.tickets = [
        {
            "Ticket ID": t.get("id", t.get("Ticket ID", "")),
            "Employee": t.get("employee", t.get("Employee", "")),
            "Issue Summary": t.get("issue", t.get("Issue Summary", "")),
            "Category": t.get("category", "General IT"),
            "Route / Action": t.get("route", "-"),
            "Policy Source": t.get("source", "-"),
            "Status": t.get("status", t.get("Status", "Open")),
        }
        for t in TICKETS
    ]


# -----------------------------
# Query Processing
# -----------------------------

def process_query(prompt: str, employee: str, email: str):
    """Submit a request to the agent and synchronize the ticket queue."""

    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt,
        }
    )

    result = st.session_state.agent.analyze(
        prompt,
        employee_name=employee,
        employee_email=email,
    )

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": result["response"],
            "result": result,
        }
    )

    # Add the generated ticket to the live queue.
    if result.get("ticket"):
        ticket_data = result["ticket"]

        next_id = (
            f"TK-{1052 + len(st.session_state.tickets) - len(TICKETS)}"
        )

        new_ticket = {
            "Ticket ID": next_id,
            "Employee": employee,
            "Issue Summary": (
                prompt[:65] + "..."
                if len(prompt) > 65
                else prompt
            ),
            "Category": ticket_data.get(
                "category",
                "IT Support",
            ),
            "Route / Action": ticket_data.get(
                "route",
                "IT Helpdesk",
            ),
            "Policy Source": ticket_data.get(
                "source",
                "KB-General",
            ),
            "Status": ticket_data.get(
                "status",
                "Open",
            ),
        }

        st.session_state.tickets.append(new_ticket)


# -----------------------------
# Sidebar
# -----------------------------

with st.sidebar:

    st.header("⚡ Evaluation Launcher")

    st.caption(
        "Select a supplied employee request to execute it "
        "through the agent."
    )

    request_lookup = {
        f"{r['id']} — {r['employee']}": r
        for r in EMPLOYEE_REQUESTS
    }

    selected_key = st.selectbox(
        "Select Benchmark Case",
        ["— Select —"] + list(request_lookup.keys()),
    )

    if selected_key != "— Select —":

        selected_request = request_lookup[selected_key]

        st.markdown(
            f"**Employee:** `{selected_request['employee']}`"
        )

        st.markdown(
            f"**Email:** `{selected_request['email']}`"
        )

        st.text_area(
            "Request Content",
            value=selected_request["request"],
            height=90,
            disabled=True,
        )

        if st.button(
            "🚀 Run Case Through Agent",
            use_container_width=True,
        ):
            process_query(
                selected_request["request"],
                selected_request["employee"],
                selected_request["email"],
            )

            st.rerun()

    st.divider()

    if st.button(
        "🧹 Clear Chat & Audit History",
        use_container_width=True,
    ):
        st.session_state.messages = []
        st.session_state.agent.audit_log = []

        st.rerun()


# -----------------------------
# Main Interface
# -----------------------------

st.title("🛠️ Veridian Corp — Internal IT Service Desk Agent")

st.caption(
    "Policy-Grounded Autonomous Resolution & Triage Engine"
)


tab_chat, tab_requests, tab_tickets, tab_policies, tab_audit = st.tabs(
    [
        "💬 Support Chat",
        "📥 Employee Requests (15)",
        "🎫 Live Ticket Queue",
        "📚 Knowledge Base",
        "🧾 Audit Trail",
    ]
)


# -----------------------------
# Agent / Chat Tab
# -----------------------------

with tab_chat:

    for message in st.session_state.messages:

        with st.chat_message(message["role"]):

            st.markdown(message["content"])

            if (
                message["role"] == "assistant"
                and "result" in message
            ):

                result = message["result"]

                c1, c2, c3 = st.columns(3)

                c1.metric(
                    "Decision",
                    result.get("decision", "N/A"),
                )

                c2.metric(
                    "Confidence",
                    f"{float(result.get('confidence', 0.0)):.2f}",
                )

                c3.metric(
                    "Source Cited",
                    result.get("source", "N/A"),
                )

                with st.expander(
                    "Inspection: Structured Ticket Payload"
                ):
                    st.json(result.get("ticket", {}))


    custom_prompt = st.chat_input(
        "Enter employee query or technical problem..."
    )

    if custom_prompt:

        process_query(
            custom_prompt,
            employee="Ad-hoc User",
            email="employee@veridian-corp.example",
        )

        st.rerun()


# -----------------------------
# Employee Requests Tab
# -----------------------------

with tab_requests:

    st.subheader(
        "Benchmark Requests — Supplied Data Pack"
    )

    st.dataframe(
        EMPLOYEE_REQUESTS,
        use_container_width=True,
        hide_index=True,
    )


# -----------------------------
# Ticket Queue Tab
# -----------------------------

with tab_tickets:

    st.subheader("Ticketing System Queue")

    st.dataframe(
        st.session_state.tickets,
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "The queue contains supplied historical tickets "
        "and tickets created during the current agent session."
    )


# -----------------------------
# Knowledge Base Tab
# -----------------------------

with tab_policies:

    st.subheader(
        "Veridian Corp Knowledge Base & Policy Governance"
    )

    for policy in POLICIES:

        with st.expander(
            f"{policy['id']} — {policy['title']}"
        ):
            st.write(policy["text"])


# -----------------------------
# Audit Trail Tab
# -----------------------------

with tab_audit:

    st.subheader("Agent Execution Audit Trail")

    if st.session_state.agent.audit_log:

        st.dataframe(
            st.session_state.agent.audit_log,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "Audit log is currently empty. "
            "Run an employee query to view trace events."
        )