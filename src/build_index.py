"""
build_index.py  –  Build the numpy vector index from scratch.

Usage:
    python src/build_index.py [--strategy fixed|paragraph|both] [--chunk-size 400]

The script:
  1. Loads both PDFs from data/raw/
  2. Chunks them using two strategies
  3. Embeds chunks with sentence-transformers (all-MiniLM-L6-v2)
  4. Saves embeddings as .npy + metadata as .json to index/
  5. Saves processed chunks to data/processed/*.jsonl for reproducibility

Storage (no external vector DB required — plain numpy files):
  index/fixed_embeddings.npy      float32 array shape (N, 384)
  index/fixed_chunks.json         list of {chunk_id, doc_id, text, metadata}
  index/paragraph_embeddings.npy
  index/paragraph_chunks.json
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    load_all_documents,
    chunk_fixed_size,
    chunk_paragraph,
    save_jsonl,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).parent.parent
DATA_RAW_DIR  = _PROJECT_ROOT / "data" / "raw"
DATA_PROC_DIR = _PROJECT_ROOT / "data" / "processed"
INDEX_DIR     = _PROJECT_ROOT / "index"
EMBED_MODEL   = "all-MiniLM-L6-v2"   # 384-dim, fast, strong English retrieval
BATCH_SIZE    = 128


# ---------------------------------------------------------------------------
# Embedding helper
# ---------------------------------------------------------------------------

def embed_chunks(model: SentenceTransformer,
                 chunks: list[dict],
                 batch_size: int = BATCH_SIZE) -> np.ndarray:
    """Return L2-normalised float32 embeddings, shape (N, 384)."""
    texts = [c["text"] for c in chunks]
    print(f"  Embedding {len(texts)} chunks in batches of {batch_size}…")
    t0 = time.time()
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,   # cosine ≡ dot product after L2-norm
    )
    print(f"  Done in {time.time() - t0:.1f}s")
    return vectors.astype(np.float32)


# ---------------------------------------------------------------------------
# Save / verify helpers
# ---------------------------------------------------------------------------

def save_index(chunks: list[dict], embeddings: np.ndarray, name: str):
    """Save embeddings (.npy) and chunk metadata (.json) to index/."""
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    emb_path   = INDEX_DIR / f"{name}_embeddings.npy"
    meta_path  = INDEX_DIR / f"{name}_chunks.json"

    np.save(str(emb_path), embeddings)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)

    print(f"  Saved {embeddings.shape[0]} vectors → {emb_path.name}  "
          f"({embeddings.nbytes / 1024 / 1024:.1f} MB)")
    print(f"  Saved chunk metadata  → {meta_path.name}")


def verify_index(name: str, model: SentenceTransformer):
    """Load saved index and do a test query to confirm readability."""
    emb_path  = INDEX_DIR / f"{name}_embeddings.npy"
    meta_path = INDEX_DIR / f"{name}_chunks.json"

    embs   = np.load(str(emb_path))
    with open(meta_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    qvec = model.encode(["test query"], normalize_embeddings=True).astype(np.float32)
    scores = (embs @ qvec.T).flatten()
    top_idx = int(np.argmax(scores))
    top_id  = chunks[top_idx]["chunk_id"]
    print(f"  ✓ {name}: loaded {embs.shape[0]} vectors, "
          f"test query OK — top chunk: {top_id[:60]}")


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def build_index(strategy: str = "both", chunk_size: int = 400, overlap: int = 50):
    print("=" * 60)
    print("Pediatric RAG — Index Builder (numpy backend)")
    print("=" * 60)

    # 1. Load documents
    print("\n[1/4] Loading documents from", DATA_RAW_DIR)
    documents = load_all_documents(str(DATA_RAW_DIR))
    print(f"  Total pages loaded: {len(documents)}")
    if not documents:
        print("ERROR: No documents found. Place PDFs in data/raw/ and retry.")
        sys.exit(1)

    # 2. Chunk
    print(f"\n[2/4] Chunking (strategy='{strategy}', size={chunk_size}, overlap={overlap})")
    fixed_chunks, para_chunks = [], []
    if strategy in ("fixed", "both"):
        fixed_chunks = chunk_fixed_size(documents, chunk_size=chunk_size, overlap=overlap)
        save_jsonl(fixed_chunks, str(DATA_PROC_DIR / "chunks_fixed.jsonl"))
        print(f"  Fixed-size chunks: {len(fixed_chunks)}")
    if strategy in ("paragraph", "both"):
        para_chunks = chunk_paragraph(documents)
        save_jsonl(para_chunks, str(DATA_PROC_DIR / "chunks_paragraph.jsonl"))
        print(f"  Paragraph chunks:  {len(para_chunks)}")

    # 3. Embed
    print(f"\n[3/4] Loading embedding model: {EMBED_MODEL}")
    model = SentenceTransformer(EMBED_MODEL)

    # 4. Save numpy index
    print(f"\n[4/4] Building numpy index → {INDEX_DIR}/")
    if strategy in ("fixed", "both") and fixed_chunks:
        print("  Embedding fixed-size chunks…")
        fixed_embs = embed_chunks(model, fixed_chunks)
        save_index(fixed_chunks, fixed_embs, "fixed")

    if strategy in ("paragraph", "both") and para_chunks:
        print("  Embedding paragraph chunks…")
        para_embs = embed_chunks(model, para_chunks)
        save_index(para_chunks, para_embs, "paragraph")

    # 5. Verify
    print("\n  Verifying index files are readable…")
    if strategy in ("fixed", "both"):
        verify_index("fixed", model)
    if strategy in ("paragraph", "both"):
        verify_index("paragraph", model)

    print("\n✓ Index build complete and verified.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the Pediatric RAG numpy index.")
    parser.add_argument("--strategy",   default="both",
                        choices=["fixed", "paragraph", "both"])
    parser.add_argument("--chunk-size", type=int, default=400)
    parser.add_argument("--overlap",    type=int, default=50)
    args = parser.parse_args()
    build_index(strategy=args.strategy,
                chunk_size=args.chunk_size,
                overlap=args.overlap)
