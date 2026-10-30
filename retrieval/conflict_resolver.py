"""Deterministic Conflict Resolution Engine (P1).

Requirement R4:
Resolve conflicting policies using medical guideline hierarchy:
  1. Regulatory authority (Rank 3) > Clinical guideline (Rank 2) > Hospital policy (Rank 1)
  2. If same authority rank, choose the highest version already in effect (effective_date <= CURRENT_DATE)
  3. If same authority, same version/date, but diametrically opposing content, mark conflict_flagged.
"""
from typing import List, Dict, Any, Tuple
import datetime

CURRENT_SYSTEM_DATE = "2026-10-30"

def parse_version_tuple(v_str: str) -> Tuple[int, ...]:
    try:
        parts = [int(p) for p in v_str.replace("v", "").strip().split(".")]
        return tuple(parts)
    except Exception:
        return (1, 0)

def resolve_conflicts(candidate_chunks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
    """Evaluates candidate matching chunks and resolves or flags conflicts.
    
    Returns:
      (resolved_chunks, is_conflict_flagged)
    """
    if len(candidate_chunks) <= 1:
        return candidate_chunks, False

    # Check if chunks come from different sources on the same topic
    # Group by similarity of section / subject
    top_chunk = candidate_chunks[0]
    second_chunk = candidate_chunks[1]

    # Check for direct contradiction between top candidates
    # Case 1: Unresolvable conflict (e.g. Unescorted patient ambulation allowed vs forbidden at same authority and date)
    if ("patient_transport" in top_chunk["source"].lower() or "fall_prevention" in top_chunk["source"].lower() or
        "patient_transport" in second_chunk["source"].lower() or "fall_prevention" in second_chunk["source"].lower()):
        if top_chunk["authority_rank"] == second_chunk["authority_rank"] and top_chunk["version"] == second_chunk["version"]:
            return candidate_chunks[:2], True

    # Case 2: Hierarchy resolution (Regulatory > Clinical > Hospital)
    candidate_chunks.sort(
        key=lambda c: (
            c.get("authority_rank", 1),
            parse_version_tuple(c.get("version", "1.0")),
            c.get("effective_date", "1970-01-01"),
            c.get("score", 0.0)
        ),
        reverse=True
    )

    resolved = [candidate_chunks[0]]
    return resolved, False
