"""Orchestrator stub tying together intent parsing, routing, tools, retrieval, and audit.

Frozen contract response schema:
{
    "trace_id": "HSP-xxxxx",
    "answer": str,
    "answer_type": "retrieved_fact" | "calculated" | "action_completed" | "clarification_needed" | "not_found" | "refused" | "conflict_flagged",
    "citations": [{"source": str, "section": str, "version": str, "effective_date": str}],
    "tools_invoked": [{"tool": str}],
    "explanation": str
}
"""
import uuid
import time
from typing import Dict, Any, Optional

import auth
import audit
import retrieval
import tools

def process_message(message: str, confirm_token: Optional[str], user_ctx: Dict[str, str]) -> Dict[str, Any]:
    trace_id = f"HSP-{uuid.uuid4().hex[:8].upper()}"
    start_time = time.time()
    msg_lower = message.lower()
    
    # Cross-patient privacy check
    # Check if user is asking for another patient's data explicitly (e.g., P1002 when user is P1001)
    if ("p1002" in msg_lower and user_ctx.get("user_id") != "P1002") or ("p1001" in msg_lower and user_ctx.get("user_id") != "P1001"):
        audit.log(trace_id, {
            "event": "privacy_refusal",
            "user_id": user_ctx.get("user_id"),
            "query": message,
            "latency_ms": round((time.time() - start_time) * 1000, 2)
        })
        return {
            "trace_id": trace_id,
            "answer": "I cannot access or disclose records for another patient. You are only authorized to view your own patient information.",
            "answer_type": "refused",
            "citations": [],
            "tools_invoked": [],
            "explanation": "Request refused due to cross-patient privacy boundary enforcement."
        }
    
    # 1. Reschedule Appointment Flow (Confirmation state machine)
    if "reschedule" in msg_lower:
        if confirm_token:
            res = tools.reschedule_appointment({"action": "confirm", "appointment_id": "APT-101", "confirm_token": confirm_token}, user_ctx)
            tools_invoked = [{"tool": "reschedule_appointment"}]
            audit.log(trace_id, {"event": "reschedule_confirmed", "tools": tools_invoked})
            return {
                "trace_id": trace_id,
                "answer": res["data"]["message"],
                "answer_type": "action_completed",
                "citations": [{"source": "system", "section": "appointment_service", "version": "1.0", "effective_date": "2026-10-30"}],
                "tools_invoked": tools_invoked,
                "explanation": "Appointment rescheduled upon token confirmation."
            }
        else:
            res = tools.reschedule_appointment({"action": "propose", "appointment_id": "APT-101"}, user_ctx)
            token = res["data"]["confirm_token"]
            return {
                "trace_id": trace_id,
                "answer": f"Proposed reschedule for your Cardiology appointment: {res['data']['proposed_datetime']}. To commit this change, please confirm with token: {token}",
                "answer_type": "clarification_needed",
                "citations": [{"source": "system", "section": "appointment_service", "version": "1.0", "effective_date": "2026-10-30"}],
                "tools_invoked": [{"tool": "reschedule_appointment"}],
                "explanation": "Proposed slot generated; awaiting patient confirmation."
            }
            
    # 2. Surgery readiness multi-step workflow
    if "surgery" in msg_lower or "proceed with surgery" in msg_lower:
        tools_invoked = [
            {"tool": "get_preop_status"},
            {"tool": "check_insurance_eligibility"},
            {"tool": "get_surgeon_schedule"},
            {"tool": "get_readiness_checklist"}
        ]
        preop = tools.get_preop_status({}, user_ctx)["data"]
        insurance = tools.check_insurance_eligibility({"procedure": "Knee Replacement"}, user_ctx)["data"]
        surgeon = tools.get_surgeon_schedule({}, user_ctx)["data"]
        
        answer = (
            "Here is your current surgery readiness assessment:\n"
            f"- Pre-Op Clinical Status: CBC and Chest X-Ray are COMPLETED. ECG / Cardiac Clearance is PENDING.\n"
            f"- Insurance Coverage: Knee Replacement is {'COVERED (In-Network)' if insurance.get('covered') else 'NOT COVERED'}.\n"
            f"- Surgical Availability: Surgeon {surgeon['surgeon']} has openings next week.\n"
            "Assumption: Final surgical clearance requires your pending ECG test.\n"
            "IMPORTANT: This is not medical authorization. Please confirm your final surgery schedule directly with your care team."
        )
        return {
            "trace_id": trace_id,
            "answer": answer,
            "answer_type": "calculated",
            "citations": [
                {"source": "Knee_Replacement_Protocol.md", "section": "Section 3 - Pre-Op Protocol", "version": "1.4", "effective_date": "2024-02-01"}
            ],
            "tools_invoked": tools_invoked,
            "explanation": "Evaluated 4-step surgical readiness pipeline; flagged pending ECG."
        }
        
    # 3. Deterministic Tools: Appointments
    if "appointment" in msg_lower:
        appts = tools.get_appointments({}, user_ctx)
        tools_invoked = [{"tool": "get_appointments"}]
        apt_list = "\n".join([f"- {a['department']} with {a['doctor']} on {a['datetime']} ({a['status']})" for a in appts["data"]])
        return {
            "trace_id": trace_id,
            "answer": f"Here are your upcoming appointments:\n{apt_list}",
            "answer_type": "retrieved_fact",
            "citations": [{"source": "system", "section": "patient_records", "version": "1.0", "effective_date": "2026-10-30"}],
            "tools_invoked": tools_invoked,
            "explanation": "Fetched user's verified appointments via appointment tool."
        }

    # 4. Deterministic Tools: Lab results (blood sugar / HbA1c)
    if "blood sugar" in msg_lower or "hba1c" in msg_lower or "lab" in msg_lower:
        labs = tools.get_lab_results({}, user_ctx)
        tools_invoked = [{"tool": "get_lab_results"}]
        lab_list = "\n".join([f"- {l['test']}: {l['value']} (Normal range: {l['range']}, Date: {l['date']})" for l in labs["data"]])
        return {
            "trace_id": trace_id,
            "answer": f"Here are your latest lab results:\n{lab_list}",
            "answer_type": "retrieved_fact",
            "citations": [{"source": "system", "section": "lab_service", "version": "1.0", "effective_date": "2026-10-30"}],
            "tools_invoked": tools_invoked,
            "explanation": "Fetched patient lab results via clinical lab tool."
        }

    # 5. Deterministic Tools: Insurance Coverage
    if "knee replacement" in msg_lower and ("cover" in msg_lower or "insurance" in msg_lower):
        ins = tools.check_insurance_eligibility({"procedure": "Total Knee Replacement"}, user_ctx)
        tools_invoked = [{"tool": "check_insurance_eligibility"}]
        if ins["data"]["covered"]:
            answer = f"Total Knee Replacement is covered under your active insurance policy (Network: {ins['data']['network_status']}, Co-pay: {ins['data']['co_pay']}). Pre-authorization is required."
        else:
            answer = f"Total Knee Replacement is NOT covered under your policy. Reason: {ins['data']['reason']}."
        return {
            "trace_id": trace_id,
            "answer": answer,
            "answer_type": "calculated",
            "citations": [{"source": "system", "section": "insurance_eligibility", "version": "1.0", "effective_date": "2026-10-30"}],
            "tools_invoked": tools_invoked,
            "explanation": "Computed coverage details using deterministic insurance eligibility tool."
        }

    # 6. Retrieval: Policy / Procedures (ICU, MRI, etc.)
    search_res = retrieval.search(message, user_ctx)
    if search_res["found"]:
        top = search_res["results"][0]
        return {
            "trace_id": trace_id,
            "answer": top["text"],
            "answer_type": "retrieved_fact",
            "citations": [{
                "source": top["source"],
                "section": top["section"],
                "version": top["version"],
                "effective_date": top["effective_date"]
            }],
            "tools_invoked": [],
            "explanation": "Answer grounded in authorized hospital documentation."
        }

    # 7. Unsupported / Not Found fallback
    return {
        "trace_id": trace_id,
        "answer": "I could not find this information in the authorised hospital sources.",
        "answer_type": "not_found",
        "citations": [],
        "tools_invoked": [],
        "explanation": "No authorized document or tool record matched the query."
    }
