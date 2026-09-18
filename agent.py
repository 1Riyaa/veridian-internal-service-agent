from datetime import datetime
import os

from dotenv import load_dotenv
from google import genai

from data import POLICIES, TICKETS

load_dotenv()

class InternalServiceAgent:
    """
    Deterministic policy-grounded agent for the Veridian Corp Assignment 2.
    It deliberately refuses to invent policy when the supplied data is insufficient.
    """

    def __init__(self):
        self.audit_log = []

        self.gemini = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY")
        )

        self.gemini_model = "gemini-3.6-flash"
        self.response_cache = {}

    def _log(self, action, details):
        self.audit_log.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "details": details
        })

    def retrieve_policy(self, text):
        t = text.lower()
        scores = {}
        keyword_map = {
            "KB-01": ["password", "locked", "lockout", "failed", "reset", "login"],
            "KB-02": ["vpn", "virtual private network", "credentials", "contractor"],
            "KB-03": ["laptop", "replacement", "replace"],
            "KB-04": ["install", "software", "application", "tool", "extension"],
            "KB-05": ["printer", "paper jam", "spooler", "print"],
            "KB-06": ["mailbox", "email", "quota", "full", "storage"],
            "KB-07": ["guest", "wifi", "wi-fi"],
            "KB-08": ["expense", "finance tool", "expense management"],
            "KB-09": ["phishing", "malware", "unauthorized access", "suspicious email"],
            "KB-10": ["home", "remote", "work from home", "monitor", "chair", "home office"],
            "Asset Management Policy": ["4-year", "refresh cycle", "asset management", "hardware"],
        }
        for p in POLICIES:
            keys = keyword_map.get(p["id"], [])
            scores[p["id"]] = sum(1 for k in keys if k in t)
        best_id = max(scores, key=scores.get)
        if scores[best_id] == 0:
            self._log("policy_retrieval", "No supplied policy matched the request.")
            return None, 0.0
        policy = next(p for p in POLICIES if p["id"] == best_id)
        confidence = min(1.0, 0.35 + 0.12 * scores[best_id])
        self._log("policy_retrieval", f"Matched {policy['id']} — {policy['title']}")
        return policy, confidence

    def understand_request(self, message):
        prompt = f"""
        You are an IT support request understanding assistant.

        Analyze the employee's request and return ONLY valid JSON with these fields:
        {{
            "intent": "short description of the request",
            "category": "one of: password, vpn, laptop, software, printer, mailbox, guest_wifi, expense, security, home_office, admin_access, unknown",
            "entities": {{}},
            "needs_clarification": true or false,
            "clarifying_question": "question or empty string"
        }}

        Do not make a policy decision.
        Do not invent company policies.
        Use only information explicitly present in the employee's message.

        Employee request:
        {message}
        """
        try:
            response = self.gemini.models.generate_content(
                model=self.gemini_model,
                contents=prompt
            )

            import json

            text = response.text.strip()

            if text.startswith("```"):
                text = text.replace("```json", "").replace("```", "").strip()

            return json.loads(text)
    
        except Exception as e:
            self._log("gemini_error", str(e))
            return None

    def generate_employee_response(self, employee_request, decision_result):
        prompt = f"""
        You are an internal IT support response writer for Veridian Corp.

        Write a concise, professional response to the employee using ONLY the
        information contained in the decision object below.

        Rules:
        - Do not invent policies, procedures, approvals, timelines, or contacts.
        - Do not change the decision.
        - Do not change the source policy.
        - Do not promise that a request will be approved.
        - If the decision is an escalation, clearly explain the next step.
        - If the decision is a follow-up, ask the required question.
        - Keep the response to 2–4 sentences.
        - Do not mention that you are an AI.

        Employee request:
        {employee_request}

        Decision object:
        {decision_result}
        """
        cache_key = (
            employee_request,
            decision_result["decision"],
            decision_result["category"],
            decision_result["source"],
            decision_result["route"]
        )

        if cache_key in self.response_cache:
            self._log("gemini_cache_hit", "Reused cached employee response.")
            return self.response_cache[cache_key]
        
        try:
            response = self.gemini.models.generate_content(
                model=self.gemini_model,
                
                contents=prompt
            )

            employee_response = response.text.strip()
            self.response_cache[cache_key] = employee_response
            return employee_response

        except Exception as e:
            self._log("gemini_response_error", str(e))
            return decision_result["response"]

    def analyze(self, message, employee_name="", employee_email=""):
        text = message.strip()
        low = text.lower()
        self.current_request = text
        self._log("input_received", text)

        # Use Gemini to understand the employee's request.
        understanding = self.understand_request(text)

        if understanding:
            self._log("gemini_understanding", understanding)

        policy, confidence = self.retrieve_policy(text)

        # Security incidents take priority.
        if any(x in low for x in ["phishing", "malware", "unauthorized access", "suspicious email"]):
            response = (
                "This is a security-sensitive request. Report the suspected phishing email, "
                "malware, or unauthorized access attempt immediately to "
                "security@veridian-corp.example. Do not forward the message to other employees."
            )
            result = self._result("Escalate to Security", "Security incident", response,
                                  "KB-09", "security@veridian-corp.example", confidence)
            self._log("decision", "Escalated security incident.")
            return result

        # Password lockout after more than 5 attempts.
        
        if "password" in low or "locked out" in low:
            import re
            match = re.search(r"\b(\d+)\s*(?:times?|attempts?|tries?)\b", low)

            if match:
                attempts = int(match.group(1))

                if attempts > 5:
                    response = "You have exceeded 5 failed attempts. Contact IT so the account can be unlocked manually. No approval is required."
                    result = self._result(
                        "Route to IT",
                        "Password lockout",
                        response,
                        "KB-01",
                        "Manual IT unlock",
                        confidence
                    )
                    self._log("decision", "Manual IT unlock required.")
                    return result

                response = "You have not exceeded the 5-attempt lockout threshold. You can use the self-service password reset process."
                result = self._result(
                    "Resolve",
                    "Password reset",
                    response,
                    "KB-01",
                    "Self-service password reset",
                    confidence
                )
                self._log("decision", "Self-service password reset.")
                return result

            if "locked out" in low:
                response = "Your account appears to be locked out. Contact IT so the account can be unlocked manually. No approval is required."
                result = self._result(
                    "Route to IT",
                    "Password lockout",
                    response,
                    "KB-01",
                    "Manual IT unlock",
                    confidence
                )
                self._log("decision", "Manual IT unlock required.")
                return result

            response = "You can use the self-service password reset process. If you have exceeded 5 failed attempts, contact IT to unlock the account manually."
            result = self._result(
                "Resolve",
                "Password reset",
                response,
                "KB-01",
                "Self-service password reset",
                confidence
            )
            self._log("decision", "Password reset guidance provided.")
            return result

    
        # Guest Wi-Fi.
        if "guest" in low and ("wifi" in low or "wi-fi" in low):
            response = "Guest Wi-Fi credentials are valid for 24 hours and can be generated by any employee from the front-desk kiosk. No IT ticket is required."
            result = self._result("Resolve", "Guest Wi-Fi", response, "KB-07", "Front-desk kiosk", confidence)
            self._log("decision", "Resolved through self-service kiosk.")
            return result

        # VPN.
        if "vpn" in low:
            if "contractor" in low:
                response = "Contractors require manager approval submitted via the access request form. VPN credentials expire every 90 days and must be renewed by the employee."
                result = self._result("Route for Approval", "Contractor VPN access", response, "KB-02", "Manager approval + access request form", confidence)
            elif "expired" in low:
                response = "VPN credentials expire every 90 days and must be renewed by the employee. The supplied policy does not specify a separate IT reset procedure for expired credentials."
                result = self._result("Resolve / Guide", "Expired VPN credentials", response, "KB-02", "Employee renewal", confidence)
            else:
                response = "VPN access is granted automatically to full-time employees. Contractors require manager approval through the access request form."
                result = self._result("Need Follow-up", "VPN access", response + "\n\nAre you a full-time employee or a contractor?", "KB-02", "Depends on employment type", confidence)
            self._log("decision", result["decision"])
            return result

        # Browser extension: policy applicability is not explicitly defined.
        if "extension" in low:
            response = (
                "The supplied IT policies do not explicitly state whether browser "
                "extensions are covered by the software policy. Please confirm "
                "whether this extension is being requested for installation on a "
                "company-managed device."
            )
            result = self._result(
                "Need Follow-up",
                "Browser extension",
                response,
                "KB-04",
                "Policy applicability requires clarification",
                0.70
            )
            self._log(
                "decision",
                "Browser extension requires clarification because policy scope is not explicit."
            ) 
            return result

        # Non-catalog software.
        if (
            ("software" in low or "tool" in low)
            and (
                "not in catalog" in low
                or "non-catalog" in low
                or "non catalog" in low
                or "approval" in low
                or "install" in low
            )
        ):
            response = (
                "Non-catalog software requires IT Security review, "
                "which typically takes 3 – 5 business days."
            )
            result = self._result(
                "Escalate / Route to Security",
                "Non-catalog software installation",
                response,
                "KB-04",
                "IT Security review required",
                confidence
            )
            self._log("decision", "Security review required.")
            return result


        
        # Non-catalog software.
        if ("software" in low or "tool" in low or "extension" in low) and ("not in" in low or "non-catalog" in low or "approval" in low or "install" in low):
            response = "Non-catalog software requires IT Security review, which takes 3–5 business days."
            result = self._result("Escalate / Route to Security", "Non-catalog software installation", response, "KB-04", "IT Security review", confidence)
            self._log("decision", "Security review required.")
            return result

        # Printer.
        if "printer" in low or "paper jam" in low:
            response = "First check the printer queue and restart the print spooler. If the issue persists after the restart, log a ticket with the printer's asset tag."
            result = self._result("Guide / Create Ticket if unresolved", "Printer troubleshooting", response, "KB-05", "Printer asset tag if unresolved", confidence)
            self._log("decision", "Provided printer troubleshooting.")
            return result

        # Mailbox.
        if "mailbox" in low or ("email" in low and ("full" in low or "quota" in low)):
            response = "The default mailbox quota is 25GB. If you are nearing quota, archive old mail. A quota increase beyond 25GB requires manager approval and is capped at 50GB."
            result = self._result("Resolve / Route for Approval", "Mailbox quota", response, "KB-06", "Manager approval for >25GB", confidence)
            self._log("decision", "Mailbox policy applied.")
            return result

        # Expense.
        if "expense" in low:
            response = "Access to the expense management tool is granted by Finance, not IT. IT can assist with login/technical issues once an account already exists."
            result = self._result("Route / Clarify", "Expense tool access or login", response, "KB-08", "Finance for access; IT for technical issue", confidence)
            self._log("decision", "Expense access routed according to policy.")
            return result

        # Home office.
        if ("home" in low or "remote" in low) and ("monitor" in low or "chair" in low or "equipment" in low):
            response = "Employees working remotely more than 3 days/week are eligible for a one-time home office equipment allowance (chair, monitor). It requires manager sign-off and Finance processing; IT handles equipment shipping only after approval."
            result = self._result("Route for Approval", "Home office equipment", response, "KB-10", "Manager sign-off + Finance processing", confidence)
            self._log("decision", "Home-office equipment routed for approval.")
            return result

        # Laptop.
        if "laptop" in low or "screen" in low or "flicker" in low:

            import re

            # Try to extract the laptop age from the employee's message.
            age_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?)", low)
            age = float(age_match.group(1)) if age_match else None

            hardware_failure = any(
                x in low
                for x in ["dead", "won't turn on", "won't turn", "completely"]
            )

            if age is not None and age >= 4:
                response = (
                    "The laptop is beyond the 4-year refresh cycle. "
                    "The Asset Management Policy provides a 4-year refresh cycle, "
                    "so this is not an early replacement outside the cycle."
                )
                result = self._result(
                    "Route to IT",
                    "Laptop replacement",
                    response,
                    "KB-03 + Asset Management Policy",
                    "Standard replacement cycle",
                    confidence
                )
                self._log("decision", "Laptop is beyond 4-year refresh cycle.")
                return result

            elif age is not None and age >= 3:
                response = (
                    "The laptop meets the 3-year eligibility threshold for replacement. "
                    "Because it is still within the 4-year Asset Management refresh cycle, "
                    "replacement outside that cycle requires Finance sign-off plus IT approval. "
                    "Requests should be raised at least 2 weeks before the intended replacement."
                )
                result = self._result(
                    "Route to IT",
                    "Laptop replacement",
                    response,
                    "KB-03 + Asset Management Policy",
                    "IT approval + Finance sign-off",
                    confidence
                )
                self._log("decision", "Laptop eligible after 3 years; early replacement requires approval.")
                return result

            elif age is not None and age < 3:
                if hardware_failure:
                    response = (
                        "The laptop is under the 3-year eligibility threshold, "
                        "but a verified hardware failure can qualify for earlier replacement. "
                        "IT should verify the hardware failure before a replacement decision."
                    )
                else:
                    response = (
                        "The laptop is under the 3-year eligibility threshold. "
                        "Earlier replacement requires a verified hardware failure, "
                        "so IT should assess the reported issue first."
                    ) 

                result = self._result(
                    "Route to IT",
                    "Laptop hardware issue",
                    response,
                    "KB-03",
                    "IT hardware verification",
                    confidence
                )
                self._log("decision", "Laptop requires IT assessment.")
                return result

            else:
                response = (
                    "Please provide the laptop age and describe the hardware problem "
                    "so the agent can determine the appropriate next step."
                )
                result = self._result(
                    "Need Follow-up",
                    "Laptop issue",
                    response,
                    "KB-03",
                    "Laptop age and hardware symptoms required",
                    confidence
                )
                self._log("decision", "Asked for laptop age and hardware symptoms.")
                return result

        # Admin access: no explicit policy supplied. Use precedent but do not invent a policy.
        if "admin access" in low or ("access" in low and "server" in low):
            response = "The supplied data does not contain a policy authorizing admin access to the finance reporting server. An existing historical ticket shows an admin access request was rejected when no business justification was provided, but that does not establish a general policy. This request should be routed to a human for authorization."
            result = self._result("Escalate to Human", "Unclear privileged access request", response, "TK-1050 (historical precedent)", "Human authorization", confidence)
            self._log("decision", "Escalated unclear privileged access request.")
            return result

        # Very vague request.
        followup = None

        if understanding:
            followup = understanding.get("clarifying_question")
        if not followup:
            followup = (
                "Could you describe what is not working? "
                "For example: VPN, password/account, laptop, printer, "
                "email/mailbox, software installation, expense tool, or something else?"
            )
        result = self._result(
            "Ask Follow-up",
            "Unclear IT issue",
            followup,
            None,
            "More issue details required",
            0.0
        )
        self._log(
            "decision",
    "       Asked Gemini-generated clarifying question because the request was underspecified."
        )
        return result
    

    def _result(self, decision, category, response, source, route, confidence):
        decision_data = {
            "decision": decision,
            "category": category,
            "response": response,
            "source": source,
            "route": route
        }

        employee_response = self.generate_employee_response(
            self.current_request,
            decision_data
        )

        if employee_response:
            response = employee_response

        return {
            "decision": decision,
            "category": category,
            "response": response,
            "source": source or "No supplied policy matched",
            "route": route,
            "confidence": round(confidence, 2),
            "ticket": {
                "category": category,
                "priority": "High" if "Security" in decision or "security" in category.lower() else "Normal",
                "route": route,
                "source": source or "None",
                "status": "Open" if decision not in ["Resolve", "Resolve / Guide"] else "Resolved/Guided"
            }
        }
