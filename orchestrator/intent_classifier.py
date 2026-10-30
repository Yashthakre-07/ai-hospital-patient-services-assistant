"""Intent Classification & Parameter Extraction Engine (P3).

Classifies patient inputs into one of the canonical intents:
- 'policy_procedure': hospital SOPs, hours, visitor rules, general policies
- 'appointment_query': viewing appointments
- 'lab_query': lab results, blood sugar, HbA1c
- 'insurance_query': procedure coverage, copays, pre-authorization
- 'surgery_workflow': surgery readiness, pre-op checks, proceeding with surgery
- 'reschedule_action': rescheduling appointments
- 'privacy_violation': attempting to query other patients
- 'unsupported': unknown or unsupported requests
"""
import re
from typing import Dict, Any

def classify_intent(message: str, user_ctx: Dict[str, str]) -> Dict[str, Any]:
    msg = message.strip()
    msg_lower = msg.lower()
    caller_id = user_ctx.get("user_id", "P1001")

    # 1. Privacy Boundary Check (Cross-patient access attempt)
    target_match = re.search(r'\b(p100[1-9]|p10[1-9][0-9])\b', msg_lower)
    if target_match:
        target_id = target_match.group(1).upper()
        if target_id != caller_id and user_ctx.get("role") != "admin":
            return {
                "intent": "privacy_violation",
                "parameters": {"target_patient_id": target_id},
                "confidence": 1.0
            }

    # 2. Reschedule Action
    if "reschedule" in msg_lower or "change appointment" in msg_lower or "move appointment" in msg_lower:
        return {
            "intent": "reschedule_action",
            "parameters": {"message": msg},
            "confidence": 0.95
        }

    # 3. Surgery Readiness Workflow
    if any(k in msg_lower for k in ["proceed with surgery", "ready for surgery", "surgery readiness", "pre-op", "preoperative"]):
        return {
            "intent": "surgery_workflow",
            "parameters": {"procedure": "Total Knee Replacement"},
            "confidence": 0.95
        }

    # 4. Lab Result Query
    if any(k in msg_lower for k in ["blood sugar", "hba1c", "lab result", "lab", "glucose", "cholesterol"]):
        test_type = "HbA1c" if "hba1c" in msg_lower else ("Fasting Blood Sugar" if "sugar" in msg_lower else None)
        return {
            "intent": "lab_query",
            "parameters": {"test": test_type},
            "confidence": 0.95
        }

    # 5. Insurance Coverage Query
    if any(k in msg_lower for k in ["covered", "coverage", "insurance", "copay", "co-pay"]):
        proc = "Total Knee Replacement" if "knee" in msg_lower else "General"
        return {
            "intent": "insurance_query",
            "parameters": {"procedure": proc},
            "confidence": 0.95
        }

    # 6. Appointments Query
    if any(k in msg_lower for k in ["appointment", "appointments", "schedule"]):
        if "mri" not in msg_lower:
            return {
                "intent": "appointment_query",
                "parameters": {},
                "confidence": 0.90
            }

    # 7. Policy / Procedure (ICU, MRI, visiting hours, masking, emergency)
    if any(k in msg_lower for k in ["visiting", "icu", "mri", "mask", "emergency", "ambulate", "policy", "procedure"]):
        return {
            "intent": "policy_procedure",
            "parameters": {"query": msg},
            "confidence": 0.90
        }

    # 8. Fallback
    return {
        "intent": "policy_procedure",
        "parameters": {"query": msg},
        "confidence": 0.50
    }
