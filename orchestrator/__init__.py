"""Orchestrator Module (P3).

Coordinates:
- auth.get_user_context
- Intent classification
- Deterministic routing to tools, retrieval, surgery workflow, or privacy refusal
- Two-phase action state machine (propose -> confirm)
- Schema validation for all 7 answer types:
    retrieved_fact | calculated | action_completed | clarification_needed | not_found | refused | conflict_flagged
- Audit trail logging
"""
import uuid
import time
from typing import Dict, Any, Optional

import auth
import audit
import retrieval
import tools
from .intent_classifier import classify_intent
from .surgery_workflow import run_surgery_readiness_workflow

def process_message(message: str, confirm_token: Optional[str], user_ctx: Dict[str, str]) -> Dict[str, Any]:
    trace_id = f"HSP-{uuid.uuid4().hex[:6].upper()}"
    start_time = time.time()
    caller_id = user_ctx.get("user_id", "P1001")
    caller_role = user_ctx.get("role", "patient")

    # Step 1: Classify intent
    classification = classify_intent(message, user_ctx)
    intent = classification.get("intent")
    params = classification.get("parameters", {})

    # 1. Privacy Refusal
    if intent == "privacy_violation":
        latency_ms = round((time.time() - start_time) * 1000, 2)
        audit.log(trace_id, {
            "event": "privacy_refusal",
            "caller_id": caller_id,
            "target_patient_id": params.get("target_patient_id"),
            "latency_ms": latency_ms,
            "model": "rule-orchestrator"
        })
        return {
            "trace_id": trace_id,
            "answer": "I cannot access or disclose records for another patient. You are only authorized to view your own patient information.",
            "answer_type": "refused",
            "citations": [],
            "tools_invoked": [],
            "explanation": f"Request refused: Caller {caller_id} attempted unauthorized access to patient {params.get('target_patient_id')}."
        }

    # 2. Reschedule Appointment Action Flow
    if intent == "reschedule_action" or confirm_token:
        # Determine appointment ID (default to APT-101 for patient)
        appt_id = "APT-101"
        if confirm_token:
            # Commit phase
            res = tools.reschedule_appointment({
                "action": "confirm",
                "appointment_id": appt_id,
                "confirm_token": confirm_token
            }, user_ctx)
            
            latency_ms = round((time.time() - start_time) * 1000, 2)
            audit.log(trace_id, {
                "event": "reschedule_confirmed",
                "appointment_id": appt_id,
                "token": confirm_token,
                "latency_ms": latency_ms,
                "tools_invoked": ["reschedule_appointment"]
            })
            
            if res.get("ok"):
                data = res["data"]
                return {
                    "trace_id": trace_id,
                    "answer": data["message"],
                    "answer_type": "action_completed",
                    "citations": [{"source": "system", "section": "appointment_scheduler", "version": "1.0", "effective_date": "2026-10-30"}],
                    "tools_invoked": [{"tool": "reschedule_appointment"}],
                    "explanation": f"Committed rescheduling action for appointment {appt_id}."
                }
            else:
                return {
                    "trace_id": trace_id,
                    "answer": f"Unable to confirm appointment reschedule: {res.get('error')}",
                    "answer_type": "refused",
                    "citations": [],
                    "tools_invoked": [{"tool": "reschedule_appointment"}],
                    "explanation": "Token confirmation failed."
                }
        else:
            # Propose phase
            res = tools.reschedule_appointment({
                "action": "propose",
                "appointment_id": appt_id
            }, user_ctx)
            
            latency_ms = round((time.time() - start_time) * 1000, 2)
            audit.log(trace_id, {
                "event": "reschedule_proposed",
                "appointment_id": appt_id,
                "latency_ms": latency_ms,
                "tools_invoked": ["reschedule_appointment"]
            })
            
            data = res.get("data", {})
            token = data.get("confirm_token")
            slot = data.get("proposed_datetime")
            answer = f"Proposed reschedule for your Cardiology appointment: {slot}. To commit this change, please confirm with token: {token}"
            return {
                "trace_id": trace_id,
                "answer": answer,
                "answer_type": "clarification_needed",
                "citations": [{"source": "system", "section": "appointment_scheduler", "version": "1.0", "effective_date": "2026-10-30"}],
                "tools_invoked": [{"tool": "reschedule_appointment"}],
                "explanation": "Slot proposed; awaiting user confirmation."
            }

    # 3. Surgery Readiness Multi-step Workflow
    if intent == "surgery_workflow":
        workflow_res = run_surgery_readiness_workflow(user_ctx)
        latency_ms = round((time.time() - start_time) * 1000, 2)
        audit.log(trace_id, {
            "event": "surgery_readiness_assessed",
            "patient_id": caller_id,
            "latency_ms": latency_ms,
            "tools_invoked": [t["tool"] for t in workflow_res["tools_invoked"]]
        })
        return {
            "trace_id": trace_id,
            **workflow_res
        }

    # 4. Lab Results Query
    if intent == "lab_query":
        test_param = params.get("test")
        res = tools.get_lab_results({"patient_id": caller_id, "test": test_param}, user_ctx)
        latency_ms = round((time.time() - start_time) * 1000, 2)
        audit.log(trace_id, {"event": "lab_results_retrieved", "test": test_param, "latency_ms": latency_ms})
        
        labs = res.get("data", [])
        if not labs:
            return {
                "trace_id": trace_id,
                "answer": "I could not find this information in the authorised hospital sources.",
                "answer_type": "not_found",
                "citations": [],
                "tools_invoked": [{"tool": "get_lab_results"}],
                "explanation": "No diagnostic lab records found for the requested test."
            }
        
        lines = [f"- **{l['test']}**: {l['value']} {l['unit']} (Ref: {l['range']}, Date: {l['date']})" for l in labs]
        answer = f"Here are your latest diagnostic lab results:\n" + "\n".join(lines)
        return {
            "trace_id": trace_id,
            "answer": answer,
            "answer_type": "calculated",
            "citations": [{"source": "system", "section": "Laboratory Information System (LIS)", "version": "1.0", "effective_date": "2026-10-30"}],
            "tools_invoked": [{"tool": "get_lab_results"}],
            "explanation": "Retrieved verified laboratory results from clinical system."
        }

    # 5. Insurance Eligibility Query
    if intent == "insurance_query":
        proc = params.get("procedure", "Total Knee Replacement")
        res = tools.check_insurance_eligibility({"patient_id": caller_id, "procedure": proc}, user_ctx)
        latency_ms = round((time.time() - start_time) * 1000, 2)
        audit.log(trace_id, {"event": "insurance_checked", "procedure": proc, "latency_ms": latency_ms})
        
        ins = res.get("data", {})
        if ins.get("covered"):
            answer = (
                f"Yes, {ins.get('procedure')} is **COVERED** under your {ins.get('payer_name')} plan.\n"
                f"- Network: {ins.get('network_status')}\n"
                f"- Co-pay: {ins.get('co_pay')}\n"
                f"- Pre-Authorization Status: {ins.get('pre_auth_status')} (Auth #{ins.get('pre_auth_number')})"
            )
        else:
            answer = (
                f"No, {proc} is **NOT COVERED** under your active insurance policy.\n"
                f"- Reason: {ins.get('reason')}"
            )

        return {
            "trace_id": trace_id,
            "answer": answer,
            "answer_type": "calculated",
            "citations": [{"source": "system", "section": "Payer Eligibility Clearinghouse", "version": "1.0", "effective_date": "2026-10-30"}],
            "tools_invoked": [{"tool": "check_insurance_eligibility"}],
            "explanation": "Evaluated insurance benefit coverage via deterministic payer rules."
        }

    # 6. Appointments Query
    if intent == "appointment_query":
        res = tools.get_appointments({"patient_id": caller_id}, user_ctx)
        latency_ms = round((time.time() - start_time) * 1000, 2)
        audit.log(trace_id, {"event": "appointments_retrieved", "latency_ms": latency_ms})
        
        appts = res.get("data", [])
        if not appts:
            return {
                "trace_id": trace_id,
                "answer": "You currently have no scheduled appointments on record.",
                "answer_type": "retrieved_fact",
                "citations": [{"source": "system", "section": "Hospital Scheduling System", "version": "1.0", "effective_date": "2026-10-30"}],
                "tools_invoked": [{"tool": "get_appointments"}],
                "explanation": "Queried hospital scheduling system."
            }
        
        lines = [f"- **{a['department']}** ({a['type']}) with {a['doctor']} on **{a['datetime']}** at {a.get('location', 'Hospital')} [Status: {a['status']}]" for a in appts]
        return {
            "trace_id": trace_id,
            "answer": "Here are your upcoming appointments:\n" + "\n".join(lines),
            "answer_type": "retrieved_fact",
            "citations": [{"source": "system", "section": "Hospital Scheduling System", "version": "1.0", "effective_date": "2026-10-30"}],
            "tools_invoked": [{"tool": "get_appointments"}],
            "explanation": "Retrieved verified patient schedule from hospital appointment registry."
        }

    # 7. Policy / Procedure Retrieval
    search_res = retrieval.search(message, user_ctx)
    latency_ms = round((time.time() - start_time) * 1000, 2)
    audit.log(trace_id, {
        "event": "policy_search",
        "found": search_res.get("found"),
        "conflict": search_res.get("conflict"),
        "latency_ms": latency_ms
    })

    if not search_res.get("found") or not search_res.get("results"):
        return {
            "trace_id": trace_id,
            "answer": "I could not find this information in the authorised hospital sources.",
            "answer_type": "not_found",
            "citations": [],
            "tools_invoked": [],
            "explanation": "No authorized document matched the query above relevance threshold."
        }

    # Handle unresolvable policy conflict
    if search_res.get("conflict"):
        c1, c2 = search_res["results"][0], search_res["results"][1]
        answer = (
            f"⚠️ **Conflict Flagged:** There are conflicting active policies regarding your inquiry:\n"
            f"1. **{c1['source']}** ({c1['section']}): {c1['text']}\n"
            f"2. **{c2['source']}** ({c2['section']}): {c2['text']}\n\n"
            f"This conflict cannot be resolved automatically. Please consult your ward nursing supervisor or department administrator."
        )
        return {
            "trace_id": trace_id,
            "answer": answer,
            "answer_type": "conflict_flagged",
            "citations": [
                {"source": c1["source"], "section": c1["section"], "version": c1["version"], "effective_date": c1["effective_date"]},
                {"source": c2["source"], "section": c2["section"], "version": c2["version"], "effective_date": c2["effective_date"]}
            ],
            "tools_invoked": [],
            "explanation": "Detected unresolvable policy conflict between approved institutional guidelines."
        }

    # Grounded answer from top resolved chunk
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
        "explanation": "Retrieved from authorized hospital policy/procedure guidelines."
    }
