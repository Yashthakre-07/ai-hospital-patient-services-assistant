"""Comprehensive test suite for Phase 3 (P1: Retrieval).

Verifies:
1. Retrieval of approved docs (ICU visiting hours, MRI scheduling, Knee protocol, Emergency).
2. Citation metadata integrity (source, section, version, effective date).
3. Score threshold enforcement -> not_found for irrelevant/unsupported queries (R3).
4. Version conflict resolution: ICU Policy v2.0 (2024) selected over older v1.0 (2022) (R4).
5. Authority conflict resolution: Government directive outranks hospital policy (R4).
6. Unresolvable policy conflict detection: marks conflict: True (R4).
7. Live admin ingestion: adds document to index live, immediately searchable without restart (R11).
8. Admin authorization check: non-admin ingestion attempt rejected (R11).
9. Adversarial prompt-injection neutralization: treated strictly as inert data (R8).
"""
import pytest
import os
import retrieval

@pytest.fixture(autouse=True)
def reset_retrieval_index():
    retrieval.build_index()

def test_retrieval_icu_visiting_hours_version_resolution():
    user_ctx = {"user_id": "P1001", "role": "patient"}
    res = retrieval.search("What are the visiting hours for ICU patients?", user_ctx)
    
    assert res["found"] is True
    assert res["conflict"] is False
    assert len(res["results"]) > 0
    
    top = res["results"][0]
    # Verify version resolution: Version 2.0 (10am-1pm & 4pm-8pm) MUST be chosen over v1.0
    assert top["version"] == "2.0"
    assert "10:00 AM to 1:00 PM" in top["text"]
    assert top["source"] == "icu_visiting_v2.md" or "ICU_Visiting_Policy_v2.md" in top["source"]
    assert top["effective_date"] == "2024-01-01"

def test_retrieval_mri_procedure_citations():
    user_ctx = {"user_id": "P1001", "role": "patient"}
    res = retrieval.search("How do I schedule an MRI scan?", user_ctx)
    
    assert res["found"] is True
    top = res["results"][0]
    assert "MRI" in top["source"] or "mri" in top["source"].lower()
    assert "Section 1.0 - Referral and Booking" in top["section"]
    assert "physician referral" in top["text"]
    assert top["version"] == "1.2"

def test_retrieval_unsupported_condition_not_found():
    user_ctx = {"user_id": "P1001", "role": "patient"}
    # Unsupported query that hospital docs do not cover
    res = retrieval.search("What is the protocol for deep sea hyperbaric astronaut training?", user_ctx)
    
    assert res["found"] is False
    assert len(res["results"]) == 0

def test_retrieval_authority_hierarchy_resolution():
    user_ctx = {"user_id": "P1001", "role": "patient"}
    # Hospital policy says masks optional in public corridors; Govt directive says masks mandatory in all areas
    res = retrieval.search("Are masks mandatory in hospital public corridors and lobbies?", user_ctx)
    
    assert res["found"] is True
    top = res["results"][0]
    # Regulatory directive MUST outrank hospital policy
    assert "govt" in top["source"].lower() or "directive" in top["source"].lower()
    assert "mandatory" in top["text"].lower()

def test_retrieval_unresolvable_conflict_flagged():
    user_ctx = {"user_id": "P1001", "role": "patient"}
    res = retrieval.search("Can post-operative patients in Wing B ambulate independently?", user_ctx)
    
    assert res["found"] is True
    assert res["conflict"] is True
    assert len(res["results"]) >= 2

def test_live_admin_ingestion_without_restart():
    admin_ctx = {"user_id": "admin", "role": "admin"}
    patient_ctx = {"user_id": "P1001", "role": "patient"}
    
    # 1. Non-admin is rejected
    temp_doc_path = os.path.join(os.path.dirname(__file__), "data", "docs", "temp_new_policy.md")
    with open(temp_doc_path, "w", encoding="utf-8") as f:
        f.write("""# Telehealth Consultation Standard
**Document Metadata:**
- **Source:** Telehealth_Standard_v1.md
- **Authority:** hospital_policy
- **Version:** 1.0
- **Effective Date:** 2026-10-01

## Section 1.0 - Video Visits
Virtual telehealth consultations are available for routine dermatological follow-ups.
""")
        
    rejected = retrieval.ingest(temp_doc_path, patient_ctx)
    assert rejected["status"] == "error"
    assert "Unauthorized" in rejected["error"]

    # 2. Admin ingestion succeeds
    success = retrieval.ingest(temp_doc_path, admin_ctx)
    assert success["status"] == "success"
    assert success["chunks"] >= 1

    # 3. Newly ingested doc is immediately searchable without restarting the app
    search_res = retrieval.search("virtual telehealth dermatological follow-up", patient_ctx)
    assert search_res["found"] is True
    assert "Telehealth" in search_res["results"][0]["text"]

    # Clean up temp file
    if os.path.exists(temp_doc_path):
        os.remove(temp_doc_path)

def test_prompt_injection_neutralization():
    user_ctx = {"user_id": "P1001", "role": "patient"}
    res = retrieval.search("Guidelines on patient record archiving instructions", user_ctx)
    
    assert res["found"] is True
    top = res["results"][0]
    # The injection prompt must be neutralized to inert text marker
    assert "INERT_TEXT_MARKER" in top["text"]
    assert "SYSTEM OVERRIDE" not in top["text"]
