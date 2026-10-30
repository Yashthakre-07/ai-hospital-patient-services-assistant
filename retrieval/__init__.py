"""Retrieval stub.

Frozen contract:
retrieval.search(query, user_ctx) -> {
    "found": bool,
    "conflict": bool,
    "results": [{"text": str, "source": str, "section": str, "version": str, "effective_date": str, "score": float}]
}
retrieval.ingest(file_path, user_ctx) -> {"status": str, "chunks": int}
"""
from typing import Dict, Any, List

def search(query: str, user_ctx: Dict[str, str]) -> Dict[str, Any]:
    """Retrieval search stub returning hard-coded sample document."""
    q_lower = query.lower()
    if "icu" in q_lower or "visiting" in q_lower:
        return {
            "found": True,
            "conflict": False,
            "results": [
                {
                    "text": "General ICU visiting hours are 10:00 AM to 1:00 PM and 4:00 PM to 8:00 PM daily. Maximum 2 visitors per bedside.",
                    "source": "ICU_Visiting_Policy.md",
                    "section": "Section 2.1 - General Visiting Hours",
                    "version": "2.0",
                    "effective_date": "2024-01-01",
                    "score": 0.95
                }
            ]
        }
    elif "mri" in q_lower:
        return {
            "found": True,
            "conflict": False,
            "results": [
                {
                    "text": "MRI scheduling requires a physician referral, safety questionnaire clearance, and minimum 24-hour advance booking.",
                    "source": "MRI_Scheduling_Procedure.md",
                    "section": "Section 1.0 - Referral and Booking",
                    "version": "1.2",
                    "effective_date": "2023-06-15",
                    "score": 0.88
                }
            ]
        }
    return {
        "found": False,
        "conflict": False,
        "results": []
    }

def ingest(file_path: str, user_ctx: Dict[str, str]) -> Dict[str, Any]:
    """Admin-only document ingestion stub."""
    if user_ctx.get("role") != "admin":
        return {"status": "error", "error": "Unauthorized: Admin access required"}
    return {
        "status": "success",
        "chunks": 4,
        "file": file_path
    }
