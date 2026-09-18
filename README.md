
# Veridian Internal Service Agent — Assignment 2

A small, policy-grounded Streamlit prototype for the AIONOS Agentic AI Factory
Assignment 2: Internal Service Agent (IT Support).

## What it demonstrates

- Understand employee IT requests
- Retrieve the relevant supplied policy
- Ask follow-up questions when information is insufficient
- Resolve simple requests
- Escalate security-sensitive or unclear requests
- Generate a structured ticket record
- Show the source used for the answer
- Maintain an audit trail

## Important design constraint

The Veridian data pack explicitly says to use only the supplied material and not invent
policies or information. This prototype follows that constraint. Where the data pack
does not provide an authorization rule, the agent routes the case to a human rather
than inventing one.

## Run locally

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

Then open the local Streamlit URL shown in the terminal.

## Suggested demo sequence

1. Guest Wi-Fi → direct resolution, no ticket needed.
2. Password locked after 6 attempts → manual IT unlock.
3. Phishing email → immediate Security escalation.
4. Non-catalog software → Security review, 3–5 business days.
5. Home-office monitor → manager sign-off + Finance.
6. "hey can you help, its not working" → clarifying question.
7. Admin access → human escalation because the supplied data does not define authorization.

## Project structure

- `app.py` — Streamlit interface
- `agent.py` — policy retrieval, decision logic, ticket creation, audit logging
- `data.py` — supplied Veridian policies, employee requests, and ticket queue
- `requirements.txt` — runtime dependency
- `README.md` — run/demo instructions

## Architecture

Employee → Chat UI → Issue classification / policy retrieval → Decision engine →
Resolve OR Follow-up OR Escalate → Structured ticket → Source citation + audit log

## Assumptions

- This is a prototype; no real corporate IT system is connected.
- Ticket creation is represented as a structured record in the UI.
- The supplied data pack is the only source of Veridian policy.
- Historical tickets are used only as precedent/context, not as new policy.
