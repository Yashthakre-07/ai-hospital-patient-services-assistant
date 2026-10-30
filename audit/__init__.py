"""Audit and Observability Module (P2).

Requirements:
- R10: Every request must generate a trace ID (HSP-xxxxx).
- Records: trace ID, sources, tools invoked, privacy checks, latency (ms), model, timestamp.
- In-memory thread-safe trace buffer + append-only JSONL log on disk.
- Queryable by trace_id for admin/compliance inspections.
"""
import time
import json
import os
from typing import Dict, Any, List, Optional

_AUDIT_STORE: List[Dict[str, Any]] = []
_AUDIT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "audit_log.jsonl")

def log(trace_id: str, event: Dict[str, Any]) -> None:
    """Logs an auditable event under a given trace_id."""
    entry = {
        "trace_id": trace_id,
        "timestamp": time.time(),
        "iso_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": event
    }
    _AUDIT_STORE.append(entry)
    
    # Also persist to append-only JSONL file
    try:
        os.makedirs(os.path.dirname(_AUDIT_FILE), exist_ok=True)
        with open(_AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

def get_trace(trace_id: str) -> List[Dict[str, Any]]:
    """Retrieves all log events for a specific trace_id."""
    return [e for e in _AUDIT_STORE if e["trace_id"] == trace_id]

def get_all_traces(limit: int = 50) -> List[Dict[str, Any]]:
    """Returns the most recent trace entries for dashboard viewing."""
    return list(reversed(_AUDIT_STORE[-limit:]))

def clear_logs() -> None:
    """Utility for unit test isolation."""
    global _AUDIT_STORE
    _AUDIT_STORE = []
