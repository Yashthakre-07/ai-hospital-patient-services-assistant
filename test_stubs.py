"""Unit test verifying that Phase 1 stubs adhere 100% to the frozen contracts
and run end-to-end via FastAPI TestClient without external dependencies.
"""
from fastapi.testclient import TestClient
import sys
import os

# Ensure local directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import app
import auth
import audit
import retrieval
import tools

client = TestClient(app)

def test_auth_contract():
    ctx = auth.get_user_context({"X-User-Id": "P1001", "X-User-Role": "patient"})
    assert ctx["user_id"] == "P1001"
    assert ctx["role"] == "patient"

def test_audit_contract():
    audit.log("HSP-TEST-01", {"event": "test_event"})
    logs = audit.get_trace("HSP-TEST-01")
    assert len(logs) == 1
    assert logs[0]["trace_id"] == "HSP-TEST-01"

def test_retrieval_contract():
    res = retrieval.search("ICU visiting hours", {"user_id": "P1001", "role": "patient"})
    assert res["found"] is True
    assert len(res["results"]) > 0
    top = res["results"][0]
    assert "source" in top
    assert "section" in top
    assert "version" in top
    assert "effective_date" in top

def test_tools_contract():
    user_ctx = {"user_id": "P1001", "role": "patient"}
    # appointments
    appts = tools.get_appointments({}, user_ctx)
    assert appts["ok"] is True
    assert len(appts["data"]) >= 1
    
    # labs
    labs = tools.get_lab_results({}, user_ctx)
    assert labs["ok"] is True
    assert any(l["test"] == "HbA1c" for l in labs["data"])
    
    # insurance
    ins = tools.check_insurance_eligibility({}, user_ctx)
    assert ins["ok"] is True
    assert "covered" in ins["data"]

def test_chat_endpoint_policy_query():
    resp = client.post(
        "/chat",
        headers={"X-User-Id": "P1001", "X-User-Role": "patient"},
        json={"message": "What are the ICU visiting hours?"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["trace_id"].startswith("HSP-")
    assert data["answer_type"] == "retrieved_fact"
    assert len(data["citations"]) >= 1
    assert "ICU_Visiting_Policy" in data["citations"][0]["source"]

def test_chat_endpoint_not_found():
    resp = client.post(
        "/chat",
        headers={"X-User-Id": "P1001", "X-User-Role": "patient"},
        json={"message": "What is the policy for astronaut training in the ward?"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer_type"] == "not_found"
    assert "could not find this information" in data["answer"]

def test_chat_endpoint_privacy_refusal():
    resp = client.post(
        "/chat",
        headers={"X-User-Id": "P1001", "X-User-Role": "patient"},
        json={"message": "Can you show me the lab results for patient P1002?"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer_type"] == "refused"
    assert "cannot access or disclose records for another patient" in data["answer"]

def test_chat_endpoint_reschedule_flow():
    # Step 1: Propose
    resp1 = client.post(
        "/chat",
        headers={"X-User-Id": "P1001", "X-User-Role": "patient"},
        json={"message": "I would like to reschedule my cardiology appointment."}
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["answer_type"] == "clarification_needed"
    assert "CONFIRM-APT-101-" in data1["answer"]
    
    # Extract generated dynamic token
    token = data1["answer"].split("token: ")[-1].strip()
    
    # Step 2: Confirm
    resp2 = client.post(
        "/chat",
        headers={"X-User-Id": "P1001", "X-User-Role": "patient"},
        json={"message": "Confirm reschedule", "confirm_token": token}
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["answer_type"] == "action_completed"
    assert "successfully rescheduled" in data2["answer"]

def test_chat_endpoint_surgery_readiness():
    resp = client.post(
        "/chat",
        headers={"X-User-Id": "P1001", "X-User-Role": "patient"},
        json={"message": "Can I proceed with surgery next week?"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer_type"] == "calculated"
    assert len(data["tools_invoked"]) == 4
    assert "NOT constitute medical or surgical authorization" in data["answer"]

