"""Deterministic tools stub.

Frozen contract:
tools.<name>(args, user_ctx) -> {"ok": bool, "data": Any, "error": str | None}

Names:
- get_appointments
- get_lab_results
- check_insurance_eligibility
- get_preop_status
- get_surgeon_schedule
- get_readiness_checklist
- drug_interaction_check
- reschedule_appointment (propose | confirm)
"""
from typing import Dict, Any

def get_appointments(args: Dict[str, Any], user_ctx: Dict[str, str]) -> Dict[str, Any]:
    target_user = args.get("patient_id", user_ctx.get("user_id"))
    if target_user != user_ctx.get("user_id"):
        return {"ok": False, "data": None, "error": f"Refused: Unauthorized access to patient {target_user}"}
    return {
        "ok": True,
        "data": [
            {"id": "APT-101", "department": "Cardiology", "doctor": "Dr. Sarah Jenkins", "datetime": "2026-11-05 10:00 AM", "status": "CONFIRMED"},
            {"id": "APT-102", "department": "Radiology (MRI)", "doctor": "Dr. David Chen", "datetime": "2026-11-08 02:30 PM", "status": "CONFIRMED"}
        ],
        "error": None
    }

def get_lab_results(args: Dict[str, Any], user_ctx: Dict[str, str]) -> Dict[str, Any]:
    target_user = args.get("patient_id", user_ctx.get("user_id"))
    if target_user != user_ctx.get("user_id"):
        return {"ok": False, "data": None, "error": f"Refused: Unauthorized access to patient {target_user}"}
    return {
        "ok": True,
        "data": [
            {"test": "HbA1c", "value": "6.2%", "unit": "%", "range": "< 5.7% (Normal), 5.7-6.4% (Prediabetes)", "date": "2026-10-25"},
            {"test": "Fasting Blood Sugar", "value": "108 mg/dL", "unit": "mg/dL", "range": "70-99 mg/dL", "date": "2026-10-25"}
        ],
        "error": None
    }

def check_insurance_eligibility(args: Dict[str, Any], user_ctx: Dict[str, str]) -> Dict[str, Any]:
    procedure = args.get("procedure", "Total Knee Replacement")
    target_user = user_ctx.get("user_id")
    if target_user == "P1003":
        return {
            "ok": True,
            "data": {"patient_id": target_user, "procedure": procedure, "covered": False, "reason": "Pre-existing condition limitation / Excluded benefit", "co_pay": "N/A"},
            "error": None
        }
    return {
        "ok": True,
        "data": {"patient_id": target_user, "procedure": procedure, "covered": True, "co_pay": "$250.00", "pre_auth_required": True, "network_status": "In-Network"},
        "error": None
    }

def get_preop_status(args: Dict[str, Any], user_ctx: Dict[str, str]) -> Dict[str, Any]:
    target_user = user_ctx.get("user_id")
    return {
        "ok": True,
        "data": {
            "patient_id": target_user,
            "tests": [
                {"name": "CBC & Metabolic Panel", "status": "COMPLETED", "date": "2026-10-25"},
                {"name": "Chest X-Ray", "status": "COMPLETED", "date": "2026-10-26"},
                {"name": "ECG / Cardiac Clearance", "status": "PENDING", "date": None}
            ]
        },
        "error": None
    }

def get_surgeon_schedule(args: Dict[str, Any], user_ctx: Dict[str, str]) -> Dict[str, Any]:
    surgeon = args.get("surgeon", "Dr. Robert Vance")
    return {
        "ok": True,
        "data": {
            "surgeon": surgeon,
            "available_slots": ["2026-11-12 08:00 AM", "2026-11-14 01:00 PM"]
        },
        "error": None
    }

def get_readiness_checklist(args: Dict[str, Any], user_ctx: Dict[str, str]) -> Dict[str, Any]:
    return {
        "ok": True,
        "data": {
            "checklist": [
                {"item": "Pre-op Clinical Tests", "status": "INCOMPLETE", "notes": "ECG pending"},
                {"item": "Insurance Pre-Authorization", "status": "APPROVED", "notes": "Auth #AUTH-88219"},
                {"item": "Surgical Team Availability", "status": "AVAILABLE", "notes": "Dr. Vance confirmed"}
            ]
        },
        "error": None
    }

def drug_interaction_check(args: Dict[str, Any], user_ctx: Dict[str, str]) -> Dict[str, Any]:
    medications = args.get("medications", [])
    return {
        "ok": True,
        "data": {
            "medications_checked": medications,
            "interactions_found": [],
            "status": "CLEAR"
        },
        "error": None
    }

def reschedule_appointment(args: Dict[str, Any], user_ctx: Dict[str, str]) -> Dict[str, Any]:
    action_type = args.get("action", "propose") # propose | confirm
    appointment_id = args.get("appointment_id", "APT-101")
    new_datetime = args.get("new_datetime", "2026-11-12 11:00 AM")
    
    if action_type == "propose":
        return {
            "ok": True,
            "data": {
                "action": "propose",
                "appointment_id": appointment_id,
                "proposed_datetime": new_datetime,
                "confirm_token": f"CONFIRM-{appointment_id}-9912",
                "message": f"Slot {new_datetime} is available. Please confirm using token."
            },
            "error": None
        }
    elif action_type == "confirm":
        token = args.get("confirm_token")
        if not token or not token.startswith("CONFIRM-"):
            return {"ok": False, "data": None, "error": "Invalid or missing confirmation token"}
        return {
            "ok": True,
            "data": {
                "action": "confirm",
                "appointment_id": appointment_id,
                "new_datetime": new_datetime,
                "status": "RESCHEDULED",
                "message": f"Appointment {appointment_id} successfully rescheduled to {new_datetime}."
            },
            "error": None
        }
    return {"ok": False, "data": None, "error": f"Unknown action: {action_type}"}
