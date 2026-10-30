# AI-Powered Hospital Patient Services Assistant
**HCLTech Future Ready AI Engineer Hackathon**

A grounded, secure, auditable, and deterministic AI assistant that answers patient queries and performs authorized healthcare actions using hospital policies, clinical protocols, patient records, insurance benefits, appointment schedules, and diagnostic reports.

---

## 1. Architectural Highlights (Option A: Grounded Orchestrator + Tools + RAG)

- **Strict Identity Context (R7)**: Patient identity is derived **only** from trusted request headers (`X-User-Id`, `X-User-Role`); never parsed or accepted from chat prompts.
- **Deterministic Healthcare Tools (R5)**: The LLM **never** calculates insurance eligibility, copays, or medical clearance. All clinical, diagnostic, and financial queries run via deterministic Python tools.
- **Grounded Retrieval & Conflict Hierarchy (R1, R2, R4)**:
  - Exact section chunking with full citations (`source`, `section`, `version`, `effective_date`).
  - Automatic conflict resolution: `regulatory_authority (Rank 3) > clinical_guideline (Rank 2) > hospital_policy (Rank 1)`, then highest active version in effect.
  - Unresolvable opposing policies at identical rank are flagged explicitly as `conflict_flagged`.
- **No Hallucination (R3)**: Strict BM25 relevance thresholding returns `not_found` when queries are unsupported by authorized documents.
- **Untrusted Content Protection (R8)**: Ingested documents and uploaded texts are treated as passive data only; adversarial prompt injections (`SYSTEM OVERRIDE`) are sanitized into inert markers.
- **Two-Phase Action State Machine (R6)**: Mutating operations (rescheduling) require a `propose` step returning a unique token, followed by an idempotent `confirm` commit.
- **Surgery Readiness Workflow (R6)**: Deterministic 5-step protocol combining guideline retrieval, pre-op test verification, insurance authorization, surgeon scheduling, and safety checklist evaluation. Always disclaims medical authorization and defers to the care team.
- **Auditability & Observability (R10)**: Every interaction generates a trace ID (`HSP-xxxxx`) recording latency, tools invoked, privacy checks, and citation metadata to `data/audit_log.jsonl`.
- **Live Admin-Only Ingestion (R11)**: Authorized administrators can upload new protocols via `POST /ingest` without restarting the server.

---

## 2. Quickstart & Running the Project

### Prerequisites
- Python 3.10+ (Tested on Python 3.12)
- All dependencies are in `requirements.txt`

### Setup and Start in 1 Command

#### Option A: Streamlit UI (Recommended for Live Hackathon Judging)
```bash
streamlit run streamlit_app.py
```
Opens interactive Streamlit dashboard at **`http://localhost:8501`**.

#### Option B: FastAPI All-in-One Server & Web UI
```bash
python app.py
```
Open **`http://localhost:8000`** in any browser.

### Running the Complete Test & Evaluation Suite
```bash
pytest -v
```
*(All 35 unit, integration, and benchmark tests run in under 1 second).*

---

## 3. Live Demo Script (Step-by-Step for Judges)

1. **ICU Visiting Hours (Policy RAG & Version Resolution)**:
   - Click Quick Scenario 1.
   - *Observation*: Returns 10:00 AM – 1:00 PM and 4:00 PM – 8:00 PM citing active version `2.0` (`ICU_Visiting_Policy_v2.md`), superseding the old 2022 policy.
2. **Latest Lab Result (Clinical Tool)**:
   - Click Quick Scenario 4.
   - *Observation*: Returns exact HbA1c (6.2%) and fasting blood sugar (108 mg/dL) with normal reference ranges from verified diagnostic records.
3. **Knee Replacement Coverage (Deterministic Insurance Eligibility)**:
   - Switch persona to `P1001`: Knee replacement is **COVERED** with $250 copay and approved pre-auth #AUTH-88219-KNEE.
   - Switch persona to `P1003`: Knee replacement is **NOT COVERED** (excluded benefit on Bronze tier).
4. **Surgery Readiness Multi-Step Assessment**:
   - Query: *"Can I proceed with surgery next week?"*
   - *Observation*: Evaluates pre-op diagnostics (CBC and Chest X-ray complete; ECG pending), confirms insurance pre-auth, checks surgeon schedule, states explicit assumptions, and reminds patient to confirm with surgical team.
5. **Two-Phase Reschedule**:
   - Query: *"Reschedule my cardiology appointment."*
   - *Observation*: Assistant generates a proposed slot and a one-time token (`CONFIRM-APT-101-xxxx`).
   - Query: *"Confirm"*
   - *Observation*: Action commits to calendar with `action_completed` badge. Submitting again demonstrates idempotency (`ALREADY_CONFIRMED`).
6. **No Hallucination (Not Found)**:
   - Query: *"What is the protocol for astronaut training in the ward?"*
   - *Observation*: Returns `not_found` badge with clean standard refusal.
7. **Cross-Patient Privacy Enforcement**:
   - As `P1001`, ask: *"Show me the lab results for patient P1002"*
   - *Observation*: Immediate `refused` badge; privacy check violation logged in audit.
8. **Live Admin Ingestion**:
   - Switch persona to `Admin`. Under Admin Panel, click "Live Ingest Protocol".
   - *Observation*: New protocol is indexed into memory live and immediately queryable without stopping the FastAPI server.
9. **Audit Trail Inspection**:
   - Click "Audit Logs" button in top navigation.
   - *Observation*: Full JSON trace history displaying trace IDs, latencies (<10ms), tools invoked, and privacy verifications.

---

## 4. Fallback Plan (If Live Presentation Environment Lacks Network)

The entire application runs **100% locally and deterministically**. It requires **zero external cloud APIs**, **zero vector database daemons**, and **zero npm dependencies**. If Wi-Fi fails or rate limits occur during judging, every single query, tool, and evaluation test continues to function identically from local in-memory storage.

---

## 5. 5-Minute Technical Defense & Q&A Cheat Sheet

| Question | Defensible Answer |
| :--- | :--- |
| **Q1: Why not let the LLM calculate insurance copays and pre-auth?** | *LLMs are probabilistic and susceptible to arithmetic or policy hallucinations. In healthcare, financial eligibility and clinical contraindications must be 100% deterministic, reproducible, and verifiable against payer contracts.* |
| **Q2: How do you defend against prompt injection in hospital docs?** | *Requirement R8: All ingested documents pass through our chunking neutralizer. Directive patterns like `SYSTEM OVERRIDE` or `ignore previous instructions` are stripped into inert markers `[DATA ONLY: INERT_TEXT_MARKER]` before indexing.* |
| **Q3: How do you handle contradictory hospital policies?** | *We apply an explicit medical guideline hierarchy: `regulatory_authority (Rank 3) > clinical_guideline (Rank 2) > hospital_policy (Rank 1)`, followed by effective date. If two policies at the same authority level directly conflict, the assistant refuses to hallucinate and issues a `conflict_flagged` response.* |
| **Q4: How is patient identity protected?** | *Zero trust on prompt text. Identity is derived strictly from verified request headers (`X-User-Id`). When a patient attempts to query another ID (`P1002`), our authorization guard immediately halts execution and logs a privacy refusal.* |

