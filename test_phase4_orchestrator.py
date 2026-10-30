"""Comprehensive unit tests for Phase 4 (P3: Orchestrator).

Verifies all 7 frozen contract answer types:
1. retrieved_fact: ICU visiting hours, MRI scheduling
2. calculated: Insurance eligibility, lab results, surgery checklist
3. action_completed: Reschedule confirmed with token
4. clarification_needed: Reschedule proposed, token provided
5. not_found: Unsupported queries
6. refused: Unauthorized cross-patient access (P1001 asking for P1002)
7. conflict_flagged: Conflicting ambulation policies
"""
import pytest
import orchestrator

def test_orchestrator_privacy_refusal():
    user_p1001 = {"user_id": "P1001", "role": "patient"}
    res = orchestrator.process_message("Show me the blood sugar and lab results for patient P1002", None, user_p1001)
    
    assert res["answer_type"] == "refused"
    assert "cannot access or disclose records for another patient" in res["answer"]
    assert res["citations"] == []

def test_orchestrator_reschedule_flow():
    user_p1001 = {"user_id": "P1001", "role": "patient"}
    
    # 1. Propose
    prop = orchestrator.process_message("Please reschedule my cardiology appointment", None, user_p1001)
    assert prop["answer_type"] == "clarification_needed"
    assert "confirm with token: CONFIRM-APT-101-" in prop["answer"]
    token = prop["answer"].split("token: ")[-1].strip()

    # 2. Confirm
    conf = orchestrator.process_message("Confirm reschedule", token, user_p1001)
    assert conf["answer_type"] == "action_completed"
    assert "successfully rescheduled" in conf["answer"]

def test_orchestrator_surgery_readiness_multistep():
    user_p1001 = {"user_id": "P1001", "role": "patient"}
    res = orchestrator.process_message("Can I proceed with surgery next week?", None, user_p1001)
    
    assert res["answer_type"] == "calculated"
    assert len(res["tools_invoked"]) == 4
    assert "Surgery Readiness Assessment" in res["answer"]
    assert "ECG / Cardiac Clearance" in res["answer"]
    assert "NOT constitute medical or surgical authorization" in res["answer"]

def test_orchestrator_insurance_eligibility():
    user_p1001 = {"user_id": "P1001", "role": "patient"}
    res = orchestrator.process_message("Is knee replacement covered under my insurance plan?", None, user_p1001)
    assert res["answer_type"] == "calculated"
    assert "COVERED" in res["answer"]
    assert "$250.00" in res["answer"]

    # P1003 not covered
    user_p1003 = {"user_id": "P1003", "role": "patient"}
    res3 = orchestrator.process_message("Is knee replacement covered under my insurance plan?", None, user_p1003)
    assert res3["answer_type"] == "calculated"
    assert "NOT COVERED" in res3["answer"]

def test_orchestrator_lab_results():
    user_p1001 = {"user_id": "P1001", "role": "patient"}
    res = orchestrator.process_message("What is my latest blood sugar and HbA1c?", None, user_p1001)
    assert res["answer_type"] == "calculated"
    assert "HbA1c" in res["answer"]
    assert "6.2" in res["answer"]

def test_orchestrator_policy_retrieval():
    user_p1001 = {"user_id": "P1001", "role": "patient"}
    res = orchestrator.process_message("What are the visiting hours for the ICU?", None, user_p1001)
    assert res["answer_type"] == "retrieved_fact"
    assert "10:00 AM to 1:00 PM" in res["answer"]
    assert res["citations"][0]["version"] == "2.0"

def test_orchestrator_conflict_flagged():
    user_p1001 = {"user_id": "P1001", "role": "patient"}
    res = orchestrator.process_message("Can post-operative patients in Wing B ambulate independently?", None, user_p1001)
    assert res["answer_type"] == "conflict_flagged"
    assert len(res["citations"]) == 2
    assert "Conflict Flagged" in res["answer"]

def test_orchestrator_not_found():
    user_p1001 = {"user_id": "P1001", "role": "patient"}
    res = orchestrator.process_message("What is the hospital policy regarding teleportation chambers?", None, user_p1001)
    assert res["answer_type"] == "not_found"
    assert "could not find this information in the authorised hospital sources" in res["answer"]
