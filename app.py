"""FastAPI Application entry point for HCLTech Hackathon Patient Assistant.

Endpoints:
- POST /chat: {message: str, confirm_token: Optional[str]} -> standard response schema
- POST /ingest: admin-only document upload stub
- GET /audit/{trace_id}: inspect trace logs
- GET /health: quick health check
"""
from typing import Optional, List, Dict, Any
import os
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field

import auth
import audit
import retrieval
import orchestrator

app = FastAPI(
    title="HCLTech AI-Powered Hospital Patient Services Assistant",
    version="1.0.0",
    description="Grounded, secure, auditable hospital assistant."
)

UI_HTML_PATH = os.path.join(os.path.dirname(__file__), "ui", "index.html")

@app.get("/", response_class=HTMLResponse)
def get_ui():
    if os.path.exists(UI_HTML_PATH):
        with open(UI_HTML_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Hospital Assistant API Online</h1>"

@app.get("/audit/recent")
def get_recent_audits():
    return audit.get_all_traces(limit=25)


class ChatRequest(BaseModel):
    message: str = Field(..., description="The user query or prompt")
    confirm_token: Optional[str] = Field(None, description="Confirmation token for actions")

class CitationModel(BaseModel):
    source: str
    section: str
    version: str
    effective_date: str

class ToolInvokedModel(BaseModel):
    tool: str

class ChatResponse(BaseModel):
    trace_id: str
    answer: str
    answer_type: str
    citations: List[CitationModel]
    tools_invoked: List[ToolInvokedModel]
    explanation: str

class IngestRequest(BaseModel):
    file_path: str

@app.get("/health")
def health():
    return {"status": "healthy", "service": "hospital-assistant"}

@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request):
    user_ctx = auth.get_user_context(request)
    resp = orchestrator.process_message(
        message=payload.message,
        confirm_token=payload.confirm_token,
        user_ctx=user_ctx
    )
    return resp

@app.post("/ingest")
def ingest_doc(payload: IngestRequest, request: Request):
    user_ctx = auth.get_user_context(request)
    result = retrieval.ingest(payload.file_path, user_ctx)
    if result.get("status") != "success":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=result.get("error", "Admin access required")
        )
    return result

@app.get("/audit/{trace_id}")
def get_audit_trail(trace_id: str):
    events = audit.get_trace(trace_id)
    return {"trace_id": trace_id, "events": events}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)

