"""Audit logger stub.

Frozen contract:
audit.log(trace_id, event) -> None
"""
import time
from typing import Dict, Any, List

_AUDIT_LOGS: List[Dict[str, Any]] = []

def log(trace_id: str, event: Dict[str, Any]) -> None:
    """Logs an auditable event with a trace_id."""
    entry = {
        "trace_id": trace_id,
        "timestamp": time.time(),
        "event": event
    }
    _AUDIT_LOGS.append(entry)

def get_trace(trace_id: str) -> List[Dict[str, Any]]:
    """Retrieves all logged events for a given trace_id."""
    return [entry for entry in _AUDIT_LOGS if entry["trace_id"] == trace_id]
