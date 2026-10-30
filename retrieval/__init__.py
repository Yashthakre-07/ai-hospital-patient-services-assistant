"""Information Retrieval Engine (P1).

Implements the frozen contract:
  retrieval.search(query, user_ctx) -> {
      "found": bool,
      "conflict": bool,
      "results": [{"text": str, "source": str, "section": str, "version": str, "effective_date": str, "score": float}]
  }
  retrieval.ingest(file_path, user_ctx) -> {"status": str, "chunks": int}

Features:
- Fast, deterministic BM25 / token-overlap scoring
- Strict relevance score threshold (R3 hallucination prevention)
- Automatic authority hierarchy & version conflict resolution (R4)
- Live admin ingestion without restart (R11)
- Prompt injection protection / data neutralization (R8)
"""
import os
import math
import re
from typing import Dict, Any, List

from .chunker import chunk_document
from .conflict_resolver import resolve_conflicts

SCORE_THRESHOLD = 0.08  # Queries scoring below this are flagged as not_found (R3)
DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "docs")

_INDEXED_CHUNKS: List[Dict[str, Any]] = []

STOPWORDS = {
    "what", "are", "the", "for", "in", "to", "and", "is", "of", "do", "how", "can", "i", "a", "an",
    "on", "at", "by", "this", "that", "it", "with", "from", "or", "as", "be", "all", "any", "guidelines", "standard", "policy"
}

def _tokenize(text: str) -> List[str]:
    # Replace punctuation and underscores with spaces to split compound names like patient_archiving_guide into patient, archiving, guide
    clean_text = re.sub(r'[_.\-]', ' ', text.lower())
    words = [w for w in re.findall(r'\b[a-zA-Z0-9]+\b', clean_text) if len(w) > 1]
    return [w for w in words if w not in STOPWORDS]

def build_index() -> None:
    """Loads and indexes all documents from data/docs."""
    global _INDEXED_CHUNKS
    _INDEXED_CHUNKS = []
    
    if not os.path.exists(DOCS_DIR):
        os.makedirs(DOCS_DIR, exist_ok=True)
        return

    for fname in sorted(os.listdir(DOCS_DIR)):
        if fname.endswith((".md", ".txt")):
            fpath = os.path.join(DOCS_DIR, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                chunks = chunk_document(content, fname)
                _INDEXED_CHUNKS.extend(chunks)
            except Exception as e:
                print(f"Error indexing {fname}: {e}")

# Build initial index on module load
build_index()

def _score_bm25(query_tokens: List[str], chunk: Dict[str, Any]) -> float:
    chunk_tokens = _tokenize(chunk.get("raw_text", ""))
    if not chunk_tokens:
        return 0.0

    score = 0.0
    matched_distinct = 0
    doc_len = len(chunk_tokens)
    avg_len = 50.0
    k1 = 1.2
    b = 0.75

    for q in query_tokens:
        count = chunk_tokens.count(q)
        if count > 0:
            matched_distinct += 1
            tf = (count * (k1 + 1)) / (count + k1 * (1 - b + b * (doc_len / avg_len)))
            score += tf

    if not query_tokens or matched_distinct == 0:
        return 0.0

    # Calculate exact term match coverage
    coverage_ratio = matched_distinct / len(query_tokens)
    
    # Require at least 25% query terms or minimum 2 terms when query has > 2 terms
    if len(query_tokens) >= 3 and matched_distinct < 2:
        return 0.0

    # Significant boost for higher coverage
    total_score = score * (coverage_ratio ** 2)
    return round(total_score, 4)

def search(query: str, user_ctx: Dict[str, str]) -> Dict[str, Any]:
    """Searches indexed hospital knowledge base with conflict resolution."""
    if not _INDEXED_CHUNKS:
        build_index()

    q_tokens = _tokenize(query)
    if not q_tokens:
        return {"found": False, "conflict": False, "results": []}

    scored_chunks = []
    for c in _INDEXED_CHUNKS:
        sc = _score_bm25(q_tokens, c)
        if sc >= SCORE_THRESHOLD:
            chunk_copy = dict(c)
            chunk_copy["score"] = sc
            scored_chunks.append(chunk_copy)

    if not scored_chunks:
        return {"found": False, "conflict": False, "results": []}

    # Sort candidates by BM25 score
    scored_chunks.sort(key=lambda x: x["score"], reverse=True)

    # Check for conflicts among top matching chunks
    top_candidates = scored_chunks[:3]
    resolved_chunks, is_conflict = resolve_conflicts(top_candidates)

    formatted_results = [
        {
            "text": c["text"],
            "source": c["source"],
            "section": c["section"],
            "version": c["version"],
            "effective_date": c["effective_date"],
            "score": c["score"]
        }
        for c in resolved_chunks
    ]

    return {
        "found": True,
        "conflict": is_conflict,
        "results": formatted_results
    }

def ingest(file_path: str, user_ctx: Dict[str, str]) -> Dict[str, Any]:
    """Requirement R11: Live admin-only ingestion without server restart."""
    caller_role = user_ctx.get("role", "patient")
    if caller_role != "admin":
        return {
            "status": "error",
            "error": "Unauthorized: Only administrators may ingest new clinical or policy documents."
        }

    if not os.path.exists(file_path):
        return {
            "status": "error",
            "error": f"File '{file_path}' does not exist on disk."
        }

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        fname = os.path.basename(file_path)
        new_chunks = chunk_document(content, fname)
        
        # Live append to running index (no restart needed!)
        global _INDEXED_CHUNKS
        _INDEXED_CHUNKS.extend(new_chunks)

        return {
            "status": "success",
            "file": fname,
            "chunks": len(new_chunks)
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Ingestion failed: {str(e)}"
        }
