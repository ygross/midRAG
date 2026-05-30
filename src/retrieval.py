"""
retrieval.py  –  Numpy-based cosine similarity retrieval.

Public API:
    retrieve(query, k=5, strategy='fixed') -> list[dict]
    retrieve_hybrid(query, k=5)            -> list[dict]
"""

import json
import sys
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).parent))

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).parent.parent
INDEX_DIR     = _PROJECT_ROOT / "index"
EMBED_MODEL   = "all-MiniLM-L6-v2"

# Module-level singletons — loaded once per process
_model:  SentenceTransformer | None = None
_index:  dict[str, dict] = {}   # strategy -> {embeddings: np.ndarray, chunks: list}


def _get_model() -> SentenceTransformer:
    """
    Return the shared SentenceTransformer embedding model, loading it on first call.

    Uses a module-level singleton so the model weights are loaded into memory
    only once per process, regardless of how many times retrieve() is called.

    Returns
    -------
    SentenceTransformer
        The loaded 'all-MiniLM-L6-v2' model (384-dimensional embeddings).
    """
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def _load_strategy(strategy: str) -> dict:
    """
    Load and cache the numpy index for a given chunking strategy.

    On first call for a strategy, reads the .npy embeddings file and the
    corresponding .json chunk metadata file from index/ and stores them in
    the module-level _index dict. Subsequent calls return the cached data
    immediately without re-reading from disk.

    Parameters
    ----------
    strategy : str
        'fixed' or 'paragraph' — determines which index files to load.

    Returns
    -------
    dict with keys:
        'embeddings' : np.ndarray  shape (N, 384), float32
        'chunks'     : list[dict]  parallel list of chunk metadata objects

    Raises
    ------
    FileNotFoundError
        If the index files for the requested strategy do not exist.
        Run 'python src/build_index.py' to generate them.
    """
    if strategy not in _index:
        emb_path  = INDEX_DIR / f"{strategy}_embeddings.npy"
        meta_path = INDEX_DIR / f"{strategy}_chunks.json"

        if not emb_path.exists() or not meta_path.exists():
            raise FileNotFoundError(
                f"Index not found for strategy '{strategy}'. "
                f"Run: python src/build_index.py --strategy {strategy}"
            )

        embeddings = np.load(str(emb_path))                       # (N, 384) float32
        with open(meta_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)

        _index[strategy] = {"embeddings": embeddings, "chunks": chunks}

    return _index[strategy]


# ---------------------------------------------------------------------------
# Public retrieve() function
# ---------------------------------------------------------------------------

def retrieve(query: str,
             k: int = 5,
             strategy: str = "fixed") -> list[dict]:
    """
    Retrieve the top-k most relevant chunks for `query` using cosine similarity.

    Parameters
    ----------
    query    : natural-language question
    k        : number of results to return
    strategy : 'fixed' or 'paragraph'

    Returns
    -------
    list of dicts:
        {
            "chunk_id": str,
            "text":     str,
            "score":    float,   # cosine similarity [0, 1]
            "metadata": dict
        }
    """
    model = _get_model()
    data  = _load_strategy(strategy)

    embeddings: np.ndarray = data["embeddings"]   # (N, 384)
    chunks: list[dict]     = data["chunks"]

    # Embed and normalise query (same as index — L2 normalised, so dot == cosine)
    qvec = model.encode([query], normalize_embeddings=True).astype(np.float32)  # (1, 384)
    scores = (embeddings @ qvec.T).flatten()                                     # (N,)

    # Top-k indices, sorted descending
    if k >= len(scores):
        top_idx = np.argsort(scores)[::-1]
    else:
        top_idx = np.argpartition(scores, -k)[-k:]
        top_idx = top_idx[np.argsort(scores[top_idx])[::-1]]

    return [
        {
            "chunk_id": chunks[i]["chunk_id"],
            "text":     chunks[i]["text"],
            "score":    round(float(scores[i]), 4),
            "metadata": chunks[i]["metadata"],
        }
        for i in top_idx
    ]


# ---------------------------------------------------------------------------
# Hybrid retrieval (merge fixed + paragraph, deduplicate by page)
# ---------------------------------------------------------------------------

def retrieve_hybrid(query: str, k: int = 5) -> list[dict]:
    """
    Retrieve from both 'fixed' and 'paragraph' strategies and merge the results.

    Runs retrieve() independently for each strategy, then deduplicates results
    by (source, page) key — keeping the higher-scoring chunk when both strategies
    return a result from the same page. Returns the top-k by score.

    Use this when you want the best of both chunking strategies, at the cost
    of running two embedding lookups instead of one.

    Parameters
    ----------
    query : str
        Natural-language question.
    k : int
        Number of results to return after merging and deduplication.

    Returns
    -------
    list[dict]
        Top-k merged results, sorted by score descending. Same format as retrieve().
    """
    fixed = retrieve(query, k=k, strategy="fixed")
    para  = retrieve(query, k=k, strategy="paragraph")

    seen, merged = {}, []
    for chunk in fixed + para:
        key = (chunk["metadata"].get("source", ""),
               chunk["metadata"].get("page", 0))
        if key not in seen or chunk["score"] > seen[key]["score"]:
            seen[key] = chunk
    return sorted(seen.values(), key=lambda x: x["score"], reverse=True)[:k]


# ---------------------------------------------------------------------------
# CLI quick-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run retrieval against the built index.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("query", nargs="*",
                        help="Natural-language question (space-separated words)")
    parser.add_argument("-k", type=int, default=3,
                        help="Number of chunks to return")
    parser.add_argument("--strategy", choices=["fixed", "paragraph", "hybrid"],
                        default="fixed",
                        help="Chunking strategy to query")
    parser.add_argument("--text-limit", type=int, default=200,
                        metavar="N",
                        help="Max characters of chunk text to print")
    args = parser.parse_args()

    query = " ".join(args.query) or "What causes fever and petechiae in children?"
    print(f"Query    : {query}")
    print(f"Strategy : {args.strategy}  |  k={args.k}\n")

    if args.strategy == "hybrid":
        results = retrieve_hybrid(query, k=args.k)
    else:
        results = retrieve(query, k=args.k, strategy=args.strategy)

    for r in results:
        print(f"[{r['score']:.3f}] {r['chunk_id']}")
        print(r["text"][:args.text_limit])
        print()
