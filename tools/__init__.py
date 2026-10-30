"""Deterministic Healthcare Tools Module (P2).

Implements all frozen contract tools:
- get_appointments
- get_lab_results
- check_insurance_eligibility
- get_preop_status
- get_surgeon_schedule
- get_readiness_checklist
- drug_interaction_check
- reschedule_appointment (propose | confirm)

Guarantees:
- Deterministic logic; zero LLM calculations or medical diagnosis.
- Cross-patient authorization checking (R7).
- Sensitive field masking (R7).
- Idempotent reschedule confirmation state machine.
"""
import os
import json
import uuid
from typing import Dict, Any, List, Optional
import auth

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "mock")

def _load_json(filename: str) -> Dict[str, Any]:
    path = os.path.join(_DATA_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def _save_json(filename: str, data: Dict[str, Any]) -> None:
    path = os.path.join(_DATA_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# In-memory store for pending appointment reschedules: token -> details
_RESCHEDULE_TOKENS: Dict[str, Dict[str, Any]] = {}

def get_appointments(args: Dict[str, Any], user_ctx: Dict[str, str]) -> Dict[str, Any]:
    """Retrieves patient appointments with cross-patient privacy guard."""
    target_patient_id = args.get("patient_id") or user_ctx.get("user_id")
    auth_check = auth.check_authorization(target_patient_id, user_ctx)
    if not auth_check["authorized"]:
        return {"ok": False, "data": None, "error": auth_check["reason"]}

    data = _load_json("appointments.json")
    all_appts = data.get("appointments", [])
    patient_appts = [a for a in all_appts if a.get("patient_id") == target_patient_id]
    
    masked_appts = [auth.mask_sensitive_data(a) for a in patient_appts]
    return {"ok": True, "data": masked_appts, "error": None}

def get_lab_results(args: Dict[str, Any], user_ctx: Dict[str, str]) -> Dict[str, Any]:
    """Retrieves diagnostic lab results (HbA1c, Fasting Blood Sugar, CBC, CMP)."""
    target_patient_id = args.get("patient_id") or user_ctx.get("user_id")
    auth_check = auth.check_authorization(target_patient_id, user_ctx)
    if not auth_check["authorized"]:
        return {"ok": False, "data": None, "error": auth_check["reason"]}

    requested_test = args.get("test")
    data = _load_json("lab_results.json")
    all_labs = data.get("lab_results", [])
    
    patient_labs = [l for l in all_labs if l.get("patient_id") == target_patient_id]
    
    if requested_test:
        test_norm = requested_test.lower().strip()
        patient_labs = [
            l for l in patient_labs 
            if test_norm in l.get("test", "").lower() or test_norm in l.get("interpretation", "").lower()
        ]

    masked_labs = [auth.mask_sensitive_data(l) for l in patient_labs]
    return {"ok": True, "data": masked_labs, "error": None}

def check_insurance_eligibility(args: Dict[str, Any], user_ctx: Dict[str, str]) -> Dict[str, Any]:
    """Performs deterministic insurance coverage and pre-authorization verification.
    
    The LLM NEVER computes this; logic is strictly rule-based.
    """
    target_patient_id = args.get("patient_id") or user_ctx.get("user_id")
    auth_check = auth.check_authorization(target_patient_id, user_ctx)
    if not auth_check["authorized"]:
        return {"ok": False, "data": None, "error": auth_check["reason"]}

    procedure = args.get("procedure", "Total Knee Replacement")
    data = _load_json("insurance.json")
    policies = data.get("policies", [])
    
    patient_policy = next((p for p in policies if p.get("patient_id") == target_patient_id), None)
    
    if not patient_policy:
        return {
            "ok": True,
            "data": {
                "patient_id": target_patient_id,
                "procedure": procedure,
                "covered": False,
                "reason": "No insurance policy found on record for this patient."
            },
            "error": None
        }

    if patient_policy.get("status") != "ACTIVE":
        return {
            "ok": True,
            "data": {
                "patient_id": target_patient_id,
                "procedure": procedure,
                "covered": False,
                "policy_status": patient_policy.get("status"),
                "reason": f"Insurance policy is {patient_policy.get('status')}. Coverage is inactive."
            },
            "error": None
        }

    # Match procedure name loosely
    coverage_map = patient_policy.get("coverage", {})
    matched_key = None
    proc_clean = procedure.lower().replace("total", "").strip()
    
    for key in coverage_map.keys():
        if proc_clean in key.lower():
            matched_key = key
            break

    if not matched_key:
        return {
            "ok": True,
            "data": {
                "patient_id": target_patient_id,
                "procedure": procedure,
                "covered": False,
                "reason": f"Procedure '{procedure}' is not listed in active policy benefits."
            },
            "error": None
        }

    benefit = coverage_map[matched_key]
    return {
        "ok": True,
        "data": {
            "patient_id": target_patient_id,
            "procedure": matched_key,
            "payer_name": patient_policy.get("payer_name"),
            "policy_number": patient_policy.get("policy_number"),
            "covered": benefit.get("covered", False),
            "co_pay": benefit.get("co_pay", "N/A"),
            "coinsurance": benefit.get("coinsurance", "N/A"),
            "network_status": benefit.get("network_status", "Unknown"),
            "pre_auth_required": benefit.get("pre_authorization_required", False),
            "pre_auth_status": benefit.get("pre_authorization_status", "NOT_REQUESTED"),
            "pre_auth_number": benefit.get("pre_auth_number", None),
            "reason": benefit.get("reason", "Standard in-network covered procedure")
        },
        "error": None
    }

def get_preop_status(args: Dict[str, Any], user_ctx: Dict[str, str]) -> Dict[str, Any]:
    """Retrieves required, completed, and pending surgical pre-op tests."""
    target_patient_id = args.get("patient_id") or user_ctx.get("user_id")
    auth_check = auth.check_authorization(target_patient_id, user_ctx)
    if not auth_check["authorized"]:
        return {"ok": False, "data": None, "error": auth_check["reason"]}

    data = _load_json("clinical_data.json")
    preop_map = data.get("preop_records", {})
    record = preop_map.get(target_patient_id)
    
    if not record:
        return {
            "ok": True,
            "data": {
                "patient_id": target_patient_id,
                "procedure": None,
                "required_tests": [],
                "completed_tests": [],
                "pending_tests": [],
                "status": "No scheduled pre-op records found"
            },
            "error": None
        }

    return {"ok": True, "data": record, "error": None}

def get_surgeon_schedule(args: Dict[str, Any], user_ctx: Dict[str, str]) -> Dict[str, Any]:
    """Returns available surgical theatre and consultation slots for surgeons."""
    surgeon = args.get("surgeon", "Dr. Robert Vance")
    data = _load_json("clinical_data.json")
    schedules = data.get("surgeon_schedules", {})
    
    schedule = schedules.get(surgeon)
    if not schedule:
        # Fallback to first available surgeon if specific name not found
        for s_name, s_data in schedules.items():
            if surgeon.lower() in s_name.lower():
                return {"ok": True, "data": {"surgeon": s_name, **s_data}, "error": None}
        return {"ok": False, "data": None, "error": f"Surgeon '{surgeon}' schedule not found"}

    return {"ok": True, "data": {"surgeon": surgeon, **schedule}, "error": None}

def get_readiness_checklist(args: Dict[str, Any], user_ctx: Dict[str, str]) -> Dict[str, Any]:
    """Deterministic checklist compilation for pre-surgical safety clearance."""
    target_patient_id = args.get("patient_id") or user_ctx.get("user_id")
    preop_res = get_preop_status({"patient_id": target_patient_id}, user_ctx)
    ins_res = check_insurance_eligibility({"patient_id": target_patient_id, "procedure": "Total Knee Replacement"}, user_ctx)
    
    preop_data = preop_res.get("data", {})
    ins_data = ins_res.get("data", {})
    
    pending_tests = preop_data.get("pending_tests", [])
    completed_tests = preop_data.get("completed_tests", [])
    
    checklist = [
        {
            "category": "Pre-Operative Diagnostics",
            "status": "CLEAR" if len(pending_tests) == 0 and len(completed_tests) > 0 else "ACTION_REQUIRED",
            "completed": [t.get("test") for t in completed_tests],
            "pending": [t.get("test") for t in pending_tests]
        },
        {
            "category": "Financial & Insurance Pre-Authorization",
            "status": "CLEAR" if ins_data.get("covered") and (not ins_data.get("pre_auth_required") or ins_data.get("pre_auth_status") == "APPROVED") else "ACTION_REQUIRED",
            "details": ins_data.get("reason", "Insurance status checked"),
            "pre_auth_number": ins_data.get("pre_auth_number")
        },
        {
            "category": "Clinical Team Confirmation",
            "status": "ACTION_REQUIRED",
            "details": "Patient must have final in-person surgical clearance with attending surgeon."
        }
    ]
    
    all_clear = all(item["status"] == "CLEAR" for item in checklist[:2])
    
    return {
        "ok": True,
        "data": {
            "patient_id": target_patient_id,
            "overall_readiness": "CONDITIONALLY_READY" if all_clear else "NOT_READY",
            "items": checklist
        },
        "error": None
    }

def drug_interaction_check(args: Dict[str, Any], user_ctx: Dict[str, str]) -> Dict[str, Any]:
    """Deterministic drug-drug interaction checker."""
    medications = args.get("medications") or args.get("medication_list") or []
    if not isinstance(medications, list) or len(medications) < 2:
        return {
            "ok": True,
            "data": {
                "medications_checked": medications,
                "interactions_found": [],
                "status": "CLEAR",
                "notes": "At least two medications are required to evaluate interactions."
            },
            "error": None
        }

    data = _load_json("clinical_data.json")
    known_interactions = data.get("drug_interactions", [])
    
    meds_lower = [m.lower().strip() for m in medications]
    flagged = []
    
    for inter in known_interactions:
        pair = [d.lower().strip() for d in inter.get("drugs", [])]
        if all(p in meds_lower for p in pair):
            flagged.append(inter)

    return {
        "ok": True,
        "data": {
            "medications_checked": medications,
            "interactions_found": flagged,
            "status": "CONTRAINDICATED" if any(f.get("severity") == "HIGH" for f in flagged) else ("CAUTION" if flagged else "CLEAR")
        },
        "error": None
    }

def reschedule_appointment(args: Dict[str, Any], user_ctx: Dict[str, str]) -> Dict[str, Any]:
    """Two-phase appointment rescheduling state machine:
    
    Phase 1 (propose):
      Validates appointment ownership, proposes a valid future slot, and generates an idempotent confirmation token.
    Phase 2 (confirm):
      Requires valid confirmation token; commits change to appointments store idempotently.
    """
    action = args.get("action", "propose").lower().strip()
    appointment_id = args.get("appointment_id", "APT-101")
    target_patient_id = user_ctx.get("user_id")

    data = _load_json("appointments.json")
    appointments = data.get("appointments", [])
    appt = next((a for a in appointments if a.get("appointment_id") == appointment_id), None)
    
    if not appt:
        return {"ok": False, "data": None, "error": f"Appointment '{appointment_id}' not found"}

    # Ownership check
    if appt.get("patient_id") != target_patient_id and user_ctx.get("role") != "admin":
        return {"ok": False, "data": None, "error": f"Unauthorized: You do not own appointment {appointment_id}"}

    if action == "propose":
        # Propose next available slot
        department = appt.get("department", "General")
        proposed_slot = "2026-11-12 11:00 AM" if "Cardio" in department else "2026-11-15 03:00 PM"
        
        token = f"CONFIRM-{appointment_id}-{uuid.uuid4().hex[:6].upper()}"
        _RESCHEDULE_TOKENS[token] = {
            "appointment_id": appointment_id,
            "patient_id": target_patient_id,
            "department": department,
            "doctor": appt.get("doctor"),
            "old_datetime": appt.get("datetime"),
            "new_datetime": proposed_slot,
            "committed": False
        }
        
        return {
            "ok": True,
            "data": {
                "action": "propose",
                "appointment_id": appointment_id,
                "current_datetime": appt.get("datetime"),
                "proposed_datetime": proposed_slot,
                "confirm_token": token,
                "instructions": f"Proposed new slot is {proposed_slot}. To confirm this change, provide confirm_token '{token}'."
            },
            "error": None
        }

    elif action == "confirm":
        token = args.get("confirm_token")
        if not token:
            return {"ok": False, "data": None, "error": "Missing confirmation token"}
            
        proposal = _RESCHEDULE_TOKENS.get(token)
        if not proposal:
            return {"ok": False, "data": None, "error": "Invalid or expired confirmation token"}

        # Idempotency check: if already committed with this token, return ALREADY_CONFIRMED
        if proposal.get("committed"):
            return {
                "ok": True,
                "data": {
                    "action": "confirm",
                    "appointment_id": appointment_id,
                    "old_datetime": proposal["old_datetime"],
                    "new_datetime": proposal["new_datetime"],
                    "status": "ALREADY_CONFIRMED",
                    "message": f"Appointment {appointment_id} is already confirmed for {proposal['new_datetime']}."
                },
                "error": None
            }

        # Validate proposal patient matches caller
        if proposal["patient_id"] != target_patient_id and user_ctx.get("role") != "admin":
            return {"ok": False, "data": None, "error": "Unauthorized: Token was generated for another patient"}

        # Commit update to JSON store
        appt["datetime"] = proposal["new_datetime"]
        appt["status"] = "RESCHEDULED"
        _save_json("appointments.json", data)
        proposal["committed"] = True

        return {
            "ok": True,
            "data": {
                "action": "confirm",
                "appointment_id": appointment_id,
                "old_datetime": proposal["old_datetime"],
                "new_datetime": proposal["new_datetime"],
                "status": "RESCHEDULED",
                "message": f"Appointment {appointment_id} successfully rescheduled to {proposal['new_datetime']}."
            },
            "error": None
        }

    return {"ok": False, "data": None, "error": f"Unsupported reschedule action: '{action}'"}
