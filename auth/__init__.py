"""User context extraction based on trusted request headers.

Frozen contract:
auth.get_user_context(request) -> {"user_id": str, "role": "patient" | "admin"}
"""
from typing import Dict, Any

def get_user_context(request_or_headers: Any) -> Dict[str, str]:
    """Extracts trusted user identity and role from headers.
    
    Defaults to user_id 'P1001' and role 'patient' if no headers are provided (stub).
    """
    user_id = "P1001"
    role = "patient"
    
    # Handle dict or FastAPI Request object
    if hasattr(request_or_headers, "headers"):
        headers = request_or_headers.headers
        user_id = headers.get("X-User-Id", headers.get("x-user-id", "P1001"))
        role = headers.get("X-User-Role", headers.get("x-user-role", "patient"))
    elif isinstance(request_or_headers, dict):
        user_id = request_or_headers.get("X-User-Id", request_or_headers.get("x-user-id", "P1001"))
        role = request_or_headers.get("X-User-Role", request_or_headers.get("x-user-role", "patient"))
        
    return {"user_id": user_id, "role": role}
