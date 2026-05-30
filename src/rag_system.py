"""
rag_system.py  –  Main RAG interface.

Public API (matches assignment spec exactly):
    answer(question: str) -> dict
"""

import sys
import re
import time
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root regardless of where the script is run from
load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent))

from retrieval  import retrieve, retrieve_hybrid
from generation import generate_answer

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_K        = 5       # number of chunks to retrieve
DEFAULT_STRATEGY = "fixed" # chunking strategy: 'fixed', 'paragraph', or 'hybrid'


# ---------------------------------------------------------------------------
# Source extraction
# ---------------------------------------------------------------------------

def _extract_cited_sources(answer_text: str,
                            retrieved_chunks: list[dict]) -> list[str]:
    """
    Parse chunk IDs that Claude cited in its answer using [Source: ...] syntax.
    Falls back to returning all retrieved chunk IDs if parsing fails.
    """
    match = re.search(r'\[Source:\s*(.*?)\]', answer_text, re.IGNORECASE)
    if match:
        raw = match.group(1)
        cited = [s.strip() for s in re.split(r'[,;]', raw) if s.strip()]
        # Validate against actual retrieved IDs
        valid_ids = {c["chunk_id"] for c in retrieved_chunks}
        return [c for c in cited if c in valid_ids] or cited
    # Fallback: all retrieved IDs
    return [c["chunk_id"] for c in retrieved_chunks]


# ---------------------------------------------------------------------------
# Main answer() function
# ---------------------------------------------------------------------------

def answer(question: str,
           k: int = DEFAULT_K,
           strategy: str = DEFAULT_STRATEGY,
           model: str = "claude-haiku-4-5-20251001") -> dict:
    """
    Answer a question using the RAG pipeline.

    Parameters
    ----------
    question : str
        Natural-language question about pediatric medicine.
    k        : int
        Number of chunks to retrieve (default: 5).
    strategy : str
        Chunking strategy to query:
        - 'fixed'     — fixed-size 400-char chunks (default)
        - 'paragraph' — paragraph-boundary chunks
        - 'hybrid'    — merge results from both fixed and paragraph indexes,
                        deduplicate by (source, page), keep highest-scoring chunk per page

    Returns
    -------
    {
        "answer":           str,          # natural-language answer with citations
        "sources":          list[str],    # chunk IDs cited
        "retrieved_chunks": list[dict]    # full chunk objects with score + metadata
    }

    Example
    -------
    >>> result = answer("What are the discharge criteria for febrile seizure?")
    >>> print(result["answer"])
    >>> print(result["sources"])

    >>> # Use hybrid retrieval for best coverage:
    >>> result = answer("What organisms cause bacterial gastroenteritis?", strategy="hybrid")
    """
    t0 = time.perf_counter()

    # 1. Retrieve relevant chunks (includes embedding the query)
    t_ret = time.perf_counter()
    if strategy == "hybrid":
        retrieved = retrieve_hybrid(question, k=k)
    else:
        retrieved = retrieve(question, k=k, strategy=strategy)
    embed_retrieve_ms = round((time.perf_counter() - t_ret) * 1000)

    # 2. Generate grounded answer
    t_gen = time.perf_counter()
    answer_text = generate_answer(question, retrieved, model=model)
    generate_ms = round((time.perf_counter() - t_gen) * 1000)

    # 3. Extract cited sources
    sources = _extract_cited_sources(answer_text, retrieved)

    return {
        "answer":           answer_text,
        "sources":          sources,
        "retrieved_chunks": retrieved,
        "_timings": {                          # underscore = internal / UI use only
            "embed_retrieve_ms": embed_retrieve_ms,
            "generate_ms":       generate_ms,
            "total_ms":          round((time.perf_counter() - t0) * 1000),
        },
    }


# ---------------------------------------------------------------------------
# Interactive demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse, json

    CLAUDE_MODELS = [
        "claude-haiku-4-5-20251001",
        "claude-sonnet-4-6",
        "claude-opus-4-7",
    ]

    parser = argparse.ArgumentParser(
        description="Run the full RAG pipeline (retrieval + generation).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("query", nargs="*",
                        help="Natural-language question (space-separated words). "
                             "Omit to run the built-in demo questions.")
    parser.add_argument("-k", type=int, default=DEFAULT_K,
                        help="Number of chunks to retrieve")
    parser.add_argument("--strategy", choices=["fixed", "paragraph", "hybrid"],
                        default=DEFAULT_STRATEGY,
                        help="Chunking strategy")
    parser.add_argument("--model", default="claude-haiku-4-5-20251001",
                        choices=CLAUDE_MODELS,
                        help="Claude model for answer generation")
    parser.add_argument("--show-chunks", action="store_true",
                        help="Print retrieved chunks and scores before the answer")
    parser.add_argument("--json", dest="as_json", action="store_true",
                        help="Dump full result as JSON")
    args = parser.parse_args()

    if args.query:
        questions = [" ".join(args.query)]
    else:
        questions = [
            "What are the discharge criteria for a child with febrile seizure?",
            "What is the initial evaluation for a newborn with respiratory distress?",
            "Which bacteria most commonly cause scrotal pain requiring urgent surgery?",
        ]

    for q in questions:
        print(f"\nQ: {q}")
        print(f"   strategy={args.strategy}  k={args.k}  model={args.model}\n")
        result = answer(q, k=args.k, strategy=args.strategy, model=args.model)

        if args.as_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            continue

        if args.show_chunks:
            print("── Retrieved chunks ──")
            for chunk in result["retrieved_chunks"]:
                print(f"  [{chunk['score']:.3f}] {chunk['chunk_id']}")
                print(f"  {chunk['text'][:200]}\n")

        print(f"A: {result['answer']}")
        print(f"Sources : {result['sources']}")
        print(f"Timings : retrieve={result['_timings']['embed_retrieve_ms']}ms  "
              f"generate={result['_timings']['generate_ms']}ms  "
              f"total={result['_timings']['total_ms']}ms")
        print("-" * 60)
