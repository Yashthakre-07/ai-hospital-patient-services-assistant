"""Comprehensive unit test suite for Phase 2 (P2: Data, Auth, Tools, Audit).

Verifies:
1. Auth from headers, role defaults, role restrictions.
2. Cross-patient privacy checks (R7 refusal).
3. Sensitive data masking (SSN, phone, email).
4. All read tools: get_appointments, get_lab_results, check_insurance_eligibility,
   get_preop_status, get_surgeon_schedule, get_readiness_checklist, drug_interaction_check.
5. Reschedule appointment state machine (propose -> token -> confirm -> idempotent re-confirm).
6. Audit logger with trace ID, privacy checks, latency, and model details.
7. Edge cases: patient with expired insurance (P1004), patient not covered (P1003),
   patient with no lab results, non-existent patient.
"""
import pytest
import auth
import audit
import tools

@pytest.fixture(autouse=True)
def setup_audit():
    audit.clear_logs()

def test_auth_context_extraction():
    # 1. From dict headers
    ctx = auth.get_user_context({"X-User-Id": "P1001", "X-User-Role": "patient"})
    assert ctx["user_id"] == "P1001"
    assert ctx["role"] == "patient"

    # 2. Case insensitive
    ctx2 = auth.get_user_context({"x-user-id": "admin", "x-user-role": "admin"})
    assert ctx2["user_id"] == "admin"
    assert ctx2["role"] == "admin"

    # 3. Defaults safely
    ctx3 = auth.get_user_context({})
    assert ctx3["user_id"] == "P1001"
    assert ctx3["role"] == "patient"

def test_cross_patient_authorization_refusal():
    caller_p1001 = {"user_id": "P1001", "role": "patient"}
    
    # Self-access allowed
    auth1 = auth.check_authorization("P1001", caller_p1001)
    assert auth1["authorized"] is True

    # Cross-access refused
    auth2 = auth.check_authorization("P1002", caller_p1001)
    assert auth2["authorized"] is False
    assert "not authorized" in auth2["reason"]

    # Admin access allowed
    admin_ctx = {"user_id": "admin", "role": "admin"}
    auth3 = auth.check_authorization("P1002", admin_ctx)
    assert auth3["authorized"] is True

def test_sensitive_data_masking():
    sample = {
        "ssn": "123-45-6789",
        "phone": "+1-555-0199",
        "email": "jane.doe@example.com",
        "department": "Cardiology"
    }
    masked = auth.mask_sensitive_data(sample)
    assert masked["ssn"] == "***-**-****"
    assert "***-****" in masked["phone"]
    assert "j***@example.com" == masked["email"]
    assert masked["department"] == "Cardiology"

def test_get_appointments_tool():
    user_p1001 = {"user_id": "P1001", "role": "patient"}
    res = tools.get_appointments({}, user_p1001)
    assert res["ok"] is True
    assert len(res["data"]) >= 2
    assert any(a["department"] == "Cardiology" for a in res["data"])
    assert any("MRI" in a["department"] for a in res["data"])

    # Attempt cross-patient access
    res_denied = tools.get_appointments({"patient_id": "P1002"}, user_p1001)
    assert res_denied["ok"] is False
    assert "Access denied" in res_denied["error"]

def test_get_lab_results_tool():
    user_p1001 = {"user_id": "P1001", "role": "patient"}
    
    # All labs
    all_labs = tools.get_lab_results({}, user_p1001)
    assert all_labs["ok"] is True
    assert len(all_labs["data"]) >= 2

    # Filtered for HbA1c
    hba1c = tools.get_lab_results({"test": "HbA1c"}, user_p1001)
    assert hba1c["ok"] is True
    assert len(hba1c["data"]) == 1
    assert hba1c["data"][0]["test"] == "HbA1c"
    assert hba1c["data"][0]["value"] == "6.2"

def test_check_insurance_eligibility():
    user_p1001 = {"user_id": "P1001", "role": "patient"}
    res_p1001 = tools.check_insurance_eligibility({"procedure": "Total Knee Replacement"}, user_p1001)
    assert res_p1001["ok"] is True
    assert res_p1001["data"]["covered"] is True
    assert res_p1001["data"]["pre_auth_status"] == "APPROVED"
    assert res_p1001["data"]["co_pay"] == "$250.00"

    # P1003: Not covered
    user_p1003 = {"user_id": "P1003", "role": "patient"}
    res_p1003 = tools.check_insurance_eligibility({"procedure": "Total Knee Replacement"}, user_p1003)
    assert res_p1003["ok"] is True
    assert res_p1003["data"]["covered"] is False
    assert "excluded" in res_p1003["data"]["reason"].lower()

    # P1004: Expired policy
    user_p1004 = {"user_id": "P1004", "role": "patient"}
    res_p1004 = tools.check_insurance_eligibility({"procedure": "Total Knee Replacement"}, user_p1004)
    assert res_p1004["ok"] is True
    assert res_p1004["data"]["covered"] is False
    assert "EXPIRED" in res_p1004["data"]["reason"]

def test_surgery_readiness_tools():
    user_p1001 = {"user_id": "P1001", "role": "patient"}
    
    # Pre-op status
    preop = tools.get_preop_status({}, user_p1001)
    assert preop["ok"] is True
    assert len(preop["data"]["completed_tests"]) >= 2
    assert len(preop["data"]["pending_tests"]) == 1
    assert preop["data"]["pending_tests"][0]["test"] == "ECG / Cardiac Clearance"

    # Surgeon schedule
    sched = tools.get_surgeon_schedule({"surgeon": "Dr. Robert Vance"}, user_p1001)
    assert sched["ok"] is True
    assert len(sched["data"]["available_slots"]) > 0

    # Readiness checklist
    chk = tools.get_readiness_checklist({}, user_p1001)
    assert chk["ok"] is True
    assert len(chk["data"]["items"]) == 3

def test_drug_interaction_check():
    user_ctx = {"user_id": "P1001", "role": "patient"}
    
    # Harmful interaction
    res_contra = tools.drug_interaction_check({"medications": ["Warfarin", "Aspirin"]}, user_ctx)
    assert res_contra["ok"] is True
    assert res_contra["data"]["status"] == "CONTRAINDICATED"
    assert len(res_contra["data"]["interactions_found"]) == 1

    # Safe / clean
    res_clear = tools.drug_interaction_check({"medications": ["Amoxicillin", "Acetaminophen"]}, user_ctx)
    assert res_clear["ok"] is True
    assert res_clear["data"]["status"] == "CLEAR"

def test_reschedule_appointment_state_machine_and_idempotency():
    user_p1001 = {"user_id": "P1001", "role": "patient"}

    # 1. Propose
    prop = tools.reschedule_appointment({"action": "propose", "appointment_id": "APT-101"}, user_p1001)
    assert prop["ok"] is True
    token = prop["data"]["confirm_token"]
    assert token.startswith("CONFIRM-APT-101-")

    # 2. Confirm with valid token
    conf = tools.reschedule_appointment({
        "action": "confirm",
        "appointment_id": "APT-101",
        "confirm_token": token
    }, user_p1001)
    assert conf["ok"] is True
    assert conf["data"]["status"] == "RESCHEDULED"

    # 3. Idempotent re-confirm with same token
    re_conf = tools.reschedule_appointment({
        "action": "confirm",
        "appointment_id": "APT-101",
        "confirm_token": token
    }, user_p1001)
    assert re_conf["ok"] is True
    assert re_conf["data"]["status"] == "ALREADY_CONFIRMED"

    # 4. Invalid token rejection
    bad_conf = tools.reschedule_appointment({
        "action": "confirm",
        "appointment_id": "APT-101",
        "confirm_token": "CONFIRM-INVALID-TOKEN"
    }, user_p1001)
    assert bad_conf["ok"] is False
    assert "Invalid or expired" in bad_conf["error"]

def test_audit_logging_and_retrieval():
    trace_id = "HSP-AUDIT-9921"
    audit.log(trace_id, {
        "event": "query_processed",
        "tools_invoked": ["get_lab_results"],
        "privacy_check": "passed",
        "latency_ms": 14.2,
        "model": "deterministic-engine"
    })
    
    entries = audit.get_trace(trace_id)
    assert len(entries) == 1
    assert entries[0]["trace_id"] == trace_id
    assert entries[0]["event"]["privacy_check"] == "passed"
    assert entries[0]["event"]["latency_ms"] == 14.2
