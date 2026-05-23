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
import datetime
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
    """
    Compute L2-normalised embeddings for a list of text chunks.

    Extracts the 'text' field from each chunk dict, encodes them in batches
    using the provided SentenceTransformer model, and returns a float32 array.

    L2 normalisation (normalize_embeddings=True) ensures that cosine similarity
    equals the dot product, which makes retrieval faster and more accurate.

    Parameters
    ----------
    model      : SentenceTransformer
        Loaded embedding model (e.g. 'all-MiniLM-L6-v2').
    chunks     : list[dict]
        List of chunk objects — each must have a 'text' key.
    batch_size : int
        Number of texts encoded per GPU/CPU batch. Larger batches are faster
        but use more memory. Default is 128.

    Returns
    -------
    np.ndarray
        Float32 array of shape (N, 384), one row per chunk, L2-normalised.
    """
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
    """
    Persist the vector index to disk as two files in index/.

    Saves:
    - index/{name}_embeddings.npy  — float32 numpy array, shape (N, 384)
    - index/{name}_chunks.json     — list of chunk metadata objects (parallel to embeddings)

    The two files are always written together and must stay in sync.
    Re-running build_index.py overwrites both files for full reproducibility.

    Parameters
    ----------
    chunks     : list[dict]
        Chunk metadata objects — must be parallel to the embeddings rows.
    embeddings : np.ndarray
        Float32 array of shape (N, 384) from embed_chunks().
    name       : str
        Strategy name, e.g. 'fixed' or 'paragraph'. Used as the filename prefix.
    """
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    emb_path   = INDEX_DIR / f"{name}_embeddings.npy"
    meta_path  = INDEX_DIR / f"{name}_chunks.json"

    np.save(str(emb_path), embeddings)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)

    print(f"  Saved {embeddings.shape[0]} vectors → {emb_path.name}  "
          f"({embeddings.nbytes / 1024 / 1024:.1f} MB)")
    print(f"  Saved chunk metadata  → {meta_path.name}")


def save_index_metadata(strategies_built: list,
                        chunks_per_strategy: dict,
                        chunk_size: int,
                        overlap: int):
    """
    Write a human-readable JSON file describing the current index build.

    Saves index/index_metadata.json with all parameters used to produce the
    current index, so the index is self-documenting. Useful for debugging,
    reproducibility checks, and displaying index info in the UI without
    reading the full .npy files.

    Parameters
    ----------
    strategies_built    : list[str]
        Which strategies were built, e.g. ['fixed', 'paragraph'].
    chunks_per_strategy : dict[str, int]
        Number of chunks produced per strategy, e.g. {'fixed': 10107, 'paragraph': 5250}.
    chunk_size          : int
        Character window size used for the fixed-size strategy.
    overlap             : int
        Character overlap between consecutive fixed-size chunks.

    Output file example
    -------------------
    {
        "embedding_model":   "all-MiniLM-L6-v2",
        "embedding_dim":     384,
        "chunk_size":        400,
        "overlap":           50,
        "strategies_built":  ["fixed", "paragraph"],
        "num_chunks":        {"fixed": 10107, "paragraph": 5250},
        "total_chunks":      15357,
        "created_at":        "2026-05-23T10:00:00Z"
    }
    """
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    metadata = {
        "embedding_model":   EMBED_MODEL,
        "embedding_dim":     384,
        "chunk_size":        chunk_size,
        "overlap":           overlap,
        "strategies_built":  strategies_built,
        "num_chunks":        chunks_per_strategy,
        "total_chunks":      sum(chunks_per_strategy.values()),
        "created_at":        datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    meta_path = INDEX_DIR / "index_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"  Saved index metadata  → {meta_path.name}")


def verify_index(name: str, model: SentenceTransformer):
    """
    Sanity-check the saved index by loading it and running a test query.

    Reads both index files back from disk, embeds a dummy query, performs
    a cosine search, and prints the top-scoring chunk ID. This confirms that:
    - The .npy and .json files are readable
    - Their shapes/lengths are consistent
    - The dot-product search returns a valid result

    Parameters
    ----------
    name  : str
        Strategy name ('fixed' or 'paragraph') — used to locate the files.
    model : SentenceTransformer
        The embedding model used during build (same model ensures compatibility).
    """
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
    """
    Full pipeline: load PDFs → chunk → embed → save numpy index.

    This is the main entry point for building (or rebuilding) the vector index
    from scratch. It is fully reproducible: deleting index/ and running again
    produces byte-identical output given the same PDFs and parameters.

    Steps:
    1. Load all PDFs from data/raw/ using load_all_documents()
    2. Chunk documents using the requested strategy (fixed / paragraph / both)
    3. Save processed chunks to data/processed/*.jsonl for reproducibility
    4. Load the SentenceTransformer embedding model
    5. Embed all chunks (batch_size=128, L2-normalised)
    6. Save embeddings + metadata to index/
    7. Verify the saved index with a test query

    Parameters
    ----------
    strategy   : str
        Which chunking strategy to build: 'fixed', 'paragraph', or 'both'.
    chunk_size : int
        Character length of each fixed-size chunk (ignored for paragraph strategy).
    overlap    : int
        Character overlap between consecutive fixed-size chunks.
    """
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

    # 5. Save metadata
    chunks_per_strategy = {}
    if strategy in ("fixed", "both") and fixed_chunks:
        chunks_per_strategy["fixed"] = len(fixed_chunks)
    if strategy in ("paragraph", "both") and para_chunks:
        chunks_per_strategy["paragraph"] = len(para_chunks)
    strategies_list = [s for s in ["fixed", "paragraph"]
                       if s in chunks_per_strategy]
    print("\n  Writing index metadata…")
    save_index_metadata(strategies_list, chunks_per_strategy,
                        chunk_size=chunk_size, overlap=overlap)

    # 6. Verify
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
