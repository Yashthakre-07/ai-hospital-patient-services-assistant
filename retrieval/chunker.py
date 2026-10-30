"""Chunking and Metadata Extraction Engine (P1).

Breaks Markdown hospital documents into structured, metadata-enriched chunks.
Treats uploaded text as DATA ONLY (neutralizing prompt injection).
"""
import re
import os
from typing import List, Dict, Any

try:
    import pypdf
except ImportError:
    pypdf = None

AUTHORITY_RANKS = {
    "regulatory_authority": 3,
    "clinical_guideline": 2,
    "hospital_policy": 1
}

def extract_text_from_file(file_path: str) -> str:
    """Extracts text content from Markdown, Plain Text, or PDF files."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        if not pypdf:
            raise RuntimeError("pypdf is required to extract text from PDF files.")
        reader = pypdf.PdfReader(file_path)
        extracted = []
        for i, page in enumerate(reader.pages):
            txt = page.extract_text() or ""
            if txt.strip():
                extracted.append(f"## Section Page {i+1}\n{txt.strip()}")
        return "\n\n".join(extracted)
    else:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

def parse_metadata(content: str) -> Dict[str, str]:
    """Extracts metadata header block from document text."""
    metadata = {
        "source": "unknown.md",
        "authority": "hospital_policy",
        "version": "1.0",
        "effective_date": "2024-01-01",
        "status": "Active"
    }
    
    meta_block = re.search(r'\*\*Document Metadata:\*\*(.*?)(?=\n##|\Z)', content, re.DOTALL)
    if meta_block:
        lines = meta_block.group(1).strip().splitlines()
        for line in lines:
            line = line.strip().lstrip("-* ").strip()
            if ":" in line:
                key, val = line.split(":", 1)
                k = key.strip().lower().replace(" ", "_")
                v = val.strip().strip('"* ')
                if k in metadata:
                    metadata[k] = v

    return metadata

def sanitize_and_neutralize_data(text: str) -> str:
    """Requirement R8: Untrusted Content Protection.
    
    Neutralizes system-override or prompt-injection attempts in document content
    by replacing directive instructions with inert text markers so they cannot
    hijack downstream LLM processing.
    """
    injection_patterns = [
        r'(?i)ignore\s+(all\s+)?(previous|prior)\s+instructions',
        r'(?i)system\s+override',
        r'(?i)disclose\s+all\s+(patient\s+)?records',
        r'(?i)reveal\s+all\s+confidential',
        r'(?i)you\s+are\s+now\s+in\s+developer\s+mode'
    ]
    cleaned = text
    for pat in injection_patterns:
        cleaned = re.sub(pat, "[DATA ONLY: INERT_TEXT_MARKER]", cleaned)
    return cleaned

def chunk_document(file_content: str, filename: str) -> List[Dict[str, Any]]:
    """Chunks document by Markdown section headers (## Section ...)."""
    meta = parse_metadata(file_content)
    if meta.get("source") == "unknown.md":
        meta["source"] = filename

    # Split on markdown section headers (## )
    sections = re.split(r'(?m)^##\s+', file_content)
    chunks = []
    
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        
        # If it's the title/metadata header before the first section, skip or extract doc title
        if sec.startswith("# ") or "**Document Metadata:**" in sec:
            continue
            
        lines = sec.splitlines()
        section_title = lines[0].strip()
        body_text = "\n".join(lines[1:]).strip()
        
        if not body_text:
            continue
            
        neutralized_body = sanitize_and_neutralize_data(body_text)
        
        chunk = {
            "source": meta["source"],
            "section": section_title,
            "authority": meta["authority"],
            "authority_rank": AUTHORITY_RANKS.get(meta["authority"], 1),
            "version": meta["version"],
            "effective_date": meta["effective_date"],
            "text": f"[{meta['source']} - {section_title}]\n{neutralized_body}",
            "raw_text": f"{meta['source']} {section_title} {neutralized_body}"
        }
        chunks.append(chunk)

    return chunks
