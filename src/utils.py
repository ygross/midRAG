"""
utils.py  –  PDF loading, text cleaning, and helper functions
for the Pediatric RAG pipeline.
"""

import re
import json
import fitz          # PyMuPDF
from pathlib import Path


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """Remove artefacts common in PDF-extracted text."""
    # Collapse repeated whitespace / newlines (but keep paragraph breaks)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    # Remove lines that are just page-number noise (e.g. "• 30 •")
    text = re.sub(r'\n[•\s\d]+\n', '\n', text)
    # Remove lone bullet characters on their own line
    text = re.sub(r'\n[•z]\s*\n', '\n', text)
    return text.strip()


# ---------------------------------------------------------------------------
# Chapter / section detection from TOC
# ---------------------------------------------------------------------------

def build_page_to_section_map(doc: fitz.Document) -> dict:
    """
    Return a dict {page_index: section_title} by walking the PDF's TOC.
    Entries are filled forward so every page carries the most-recent heading.
    """
    toc = doc.get_toc()   # [[level, title, page], ...]
    mapping = {}
    for level, title, page in toc:
        zero_idx = page - 1
        if zero_idx >= 0:
            mapping[zero_idx] = title.replace('\n', ' ').strip()

    # Forward-fill
    filled = {}
    current = "Front Matter"
    for pg in range(len(doc)):
        if pg in mapping:
            current = mapping[pg]
        filled[pg] = current
    return filled


# ---------------------------------------------------------------------------
# Document loading
# ---------------------------------------------------------------------------

def load_pdf(pdf_path: str, doc_id_prefix: str) -> list[dict]:
    """
    Load a PDF and return a list of page-level documents.

    Each document:
        {
            "doc_id":   "kliegman_p003",
            "text":     "...",
            "metadata": {
                "source":  "Kliegman_Pediatric.pdf",
                "page":    3,
                "section": "Chapter 2 Rhinorrhea",
                "doc_id_prefix": "kliegman"
            }
        }
    Only pages with meaningful text (> 50 characters) are included.
    """
    path = Path(pdf_path)
    doc = fitz.open(str(path))
    section_map = build_page_to_section_map(doc)

    documents = []
    for pg_idx in range(len(doc)):
        raw_text = doc[pg_idx].get_text()
        text = clean_text(raw_text)
        if len(text) < 50:          # skip empty / image-only pages
            continue
        doc_id = f"{doc_id_prefix}_p{pg_idx + 1:04d}"
        documents.append({
            "doc_id": doc_id,
            "text": text,
            "metadata": {
                "source":        path.name,
                "page":          pg_idx + 1,
                "section":       section_map.get(pg_idx, "Unknown"),
                "doc_id_prefix": doc_id_prefix,
            }
        })
    doc.close()
    return documents


def load_all_documents(data_dir: str = "data/raw") -> list[dict]:
    """
    Load all PDFs found in data_dir.
    Assigns a short prefix based on filename.
    """
    data_path = Path(data_dir)
    prefix_map = {
        "Kliegman": "kliegman",
        "Case-Based": "aap",
    }
    all_docs = []
    for pdf_file in sorted(data_path.glob("*.pdf")):
        prefix = "doc"
        for keyword, short in prefix_map.items():
            if keyword.lower() in pdf_file.name.lower() or keyword in pdf_file.name:
                prefix = short
                break
        print(f"  Loading {pdf_file.name} → prefix='{prefix}'")
        docs = load_pdf(str(pdf_file), prefix)
        all_docs.extend(docs)
        print(f"    → {len(docs)} pages loaded")
    return all_docs


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_fixed_size(documents: list[dict],
                     chunk_size: int = 400,
                     overlap: int = 50) -> list[dict]:
    """
    Strategy 1 – Fixed-size character chunking with overlap.

    Splits each document's text into chunks of `chunk_size` characters,
    stepping forward by (chunk_size - overlap) each time.

    Rationale: Simple, reproducible, works well for the Kliegman decision-tree
    pages where content is dense and short.  chunk_size=400 keeps each chunk
    within one context window step while preserving enough medical terminology.
    """
    chunks = []
    step = chunk_size - overlap
    for doc in documents:
        text = doc["text"]
        start = 0
        idx = 0
        while start < len(text):
            end = start + chunk_size
            chunk_text = text[start:end].strip()
            if len(chunk_text) > 30:          # skip trivially short tail chunks
                chunk_id = f"{doc['doc_id']}_fixed_{idx:03d}"
                chunks.append({
                    "chunk_id": chunk_id,
                    "doc_id":   doc["doc_id"],
                    "text":     chunk_text,
                    "metadata": {
                        **doc["metadata"],
                        "chunk_strategy": "fixed",
                        "chunk_index":    idx,
                    }
                })
            start += step
            idx += 1
    return chunks


def chunk_paragraph(documents: list[dict],
                    min_len: int = 100,
                    max_len: int = 700) -> list[dict]:
    """
    Strategy 2 – Paragraph-aware chunking.

    Splits on double-newlines (natural paragraph breaks from PDF extraction),
    then merges very short paragraphs together until they exceed min_len,
    and splits very long paragraphs at sentence boundaries to stay below max_len.

    Rationale: The AAP Case-Based Guide is structured as Q&A paragraphs.
    Preserving paragraph boundaries keeps entire clinical reasoning steps
    in one chunk, which improves answer coherence for case-based questions.
    """
    def split_long(text: str, max_len: int) -> list[str]:
        """Split a too-long string at sentence ends."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        parts, buf = [], ""
        for s in sentences:
            if len(buf) + len(s) + 1 <= max_len:
                buf = (buf + " " + s).strip()
            else:
                if buf:
                    parts.append(buf)
                buf = s
        if buf:
            parts.append(buf)
        return parts or [text[:max_len]]

    chunks = []
    for doc in documents:
        paragraphs = [p.strip() for p in re.split(r'\n{2,}', doc["text"]) if p.strip()]
        merged, buf = [], ""
        for para in paragraphs:
            candidate = (buf + "\n\n" + para).strip() if buf else para
            if len(candidate) <= max_len:
                buf = candidate
                if len(buf) >= min_len:
                    merged.append(buf)
                    buf = ""
            else:
                if buf:
                    merged.append(buf)
                    buf = ""
                for part in split_long(para, max_len):
                    merged.append(part)
        if buf:
            merged.append(buf)

        for idx, chunk_text in enumerate(merged):
            if len(chunk_text) > 30:
                chunk_id = f"{doc['doc_id']}_para_{idx:03d}"
                chunks.append({
                    "chunk_id": chunk_id,
                    "doc_id":   doc["doc_id"],
                    "text":     chunk_text,
                    "metadata": {
                        **doc["metadata"],
                        "chunk_strategy": "paragraph",
                        "chunk_index":    idx,
                    }
                })
    return chunks


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def save_jsonl(records: list[dict], path: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"  Saved {len(records)} records → {path}")


def load_jsonl(path: str) -> list[dict]:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records
