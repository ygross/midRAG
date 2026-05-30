"""
run_eval.py  –  Evaluation script for the Pediatric RAG pipeline.

Usage:
    python eval/run_eval.py [--strategy fixed|paragraph] [--k 5] [--limit 50]

Metrics computed:
    Hit@k   : fraction of questions where at least one correct source page
              appears in the top-k retrieved chunks
    Precision@k : fraction of retrieved chunks that come from the correct page
    Manual accuracy (printed for the first 10 answers for human inspection)

Ablation table:
    The script automatically runs four ablation experiments:
        1. chunk_size=300 vs chunk_size=700 (fixed strategy)
        2. top-k=3 vs top-k=8
    Results are printed as a comparison table.
"""

import sys
import json
import time
import argparse
import statistics
from pathlib import Path

# Load .env from project root before importing src modules
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

# Make src/ importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from rag_system import answer
from retrieval  import retrieve

_PROJECT_ROOT = Path(__file__).parent.parent
GOLD_PATH     = Path(__file__).parent / "gold_set.jsonl"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_gold_set(path: Path = GOLD_PATH) -> list[dict]:
    """
    Load the gold evaluation set from a JSON Lines file.

    Each line in the file is a JSON object representing one evaluation question
    with the following fields:
    - 'question'            : str  — the evaluation question
    - 'reference_answer'    : str  — expected answer (for human inspection)
    - 'must_cite_chunk_ids' : list[str] — gold chunk IDs the system should retrieve
    - 'category'            : str  — question type (factual/numerical/temporal/etc.)

    Parameters
    ----------
    path : Path
        Path to the gold set .jsonl file. Defaults to eval/gold_set.jsonl.

    Returns
    -------
    list[dict]
        List of evaluation question objects.
    """
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def extract_correct_pages(chunk_ids: list[str]) -> set[int]:
    """
    Extract page numbers from gold chunk IDs like 'aap_p0051_fixed_000'.
    Used for soft matching when exact chunk IDs may differ slightly.
    """
    pages = set()
    for cid in chunk_ids:
        parts = cid.split("_")
        for part in parts:
            if part.startswith("p") and part[1:].isdigit():
                pages.add(int(part[1:]))
    return pages


def extract_correct_sources(chunk_ids: list[str]) -> set[str]:
    """Extract the source prefix (e.g., 'aap', 'kliegman') from gold chunk IDs."""
    return {cid.split("_")[0] for cid in chunk_ids}


def chunk_hits_at_k(retrieved: list[dict],
                    gold_chunk_ids: list[str]) -> bool:
    """
    Return True if any retrieved chunk matches a gold chunk ID exactly
    OR comes from the same source + approximate page range (±2 pages).

    The ±2-page soft match handles slight chunking boundary differences.
    """
    # Exact match first
    retrieved_ids = {c["chunk_id"] for c in retrieved}
    if retrieved_ids & set(gold_chunk_ids):
        return True

    # Soft match: same source + page within ±2
    gold_pages   = extract_correct_pages(gold_chunk_ids)
    gold_sources = extract_correct_sources(gold_chunk_ids)
    for chunk in retrieved:
        src  = chunk["metadata"].get("doc_id_prefix", "")
        page = int(chunk["metadata"].get("page", 0))
        if src in gold_sources:
            for gp in gold_pages:
                if abs(page - gp) <= 2:
                    return True
    return False


# ---------------------------------------------------------------------------
# Single evaluation run
# ---------------------------------------------------------------------------

def evaluate(gold: list[dict],
             k: int = 5,
             strategy: str = "fixed",
             limit: int | None = None,
             verbose: bool = True,
             model: str = "claude-haiku-4-5-20251001") -> dict:
    """
    Run the RAG pipeline on the gold question set and compute retrieval metrics.

    For each question in the gold set:
    1. Calls answer() to get the top-k retrieved chunks and generated answer
    2. Computes Hit@k using chunk_hits_at_k() (exact + soft ±2-page match)
    3. Computes Precision@k — fraction of retrieved chunks from the correct source
    4. Records latency per question

    Prints the first 10 answers for manual quality inspection (Correct /
    Partially correct / Incorrect / Hallucinated), then prints aggregate metrics
    and a per-category breakdown.

    Parameters
    ----------
    gold     : list[dict]
        Gold evaluation questions loaded by load_gold_set().
    k        : int
        Number of chunks to retrieve per question.
    strategy : str
        Chunking strategy: 'fixed' or 'paragraph'.
    limit    : int | None
        If set, only evaluate the first N questions (useful for quick tests).
    verbose  : bool
        If True, prints individual question results for the first 10 questions.

    Returns
    -------
    dict with keys:
        'hit_at_k'       : float  — fraction of questions with a correct chunk in top-k
        'precision_at_k' : float  — average fraction of retrieved chunks from correct source
        'mean_latency'   : float  — average seconds per question
        'strategy'       : str
        'k'              : int
        'n'              : int    — number of questions evaluated
    """
    if limit:
        gold = gold[:limit]

    hits         = 0
    total_precis = 0.0
    latencies    = []
    category_hits: dict[str, list[bool]] = {}

    print(f"\n{'='*65}")
    print(f"Evaluation  |  strategy={strategy}  k={k}  n={len(gold)}")
    print(f"{'='*65}")

    for i, item in enumerate(gold):
        question    = item["question"]
        gold_ids    = item.get("must_cite_chunk_ids", [])
        category    = item.get("category", "unknown")
        ref_answer  = item.get("reference_answer", "")

        t0 = time.time()
        result = answer(question, k=k, strategy=strategy, model=model)
        latency = time.time() - t0
        latencies.append(latency)

        retrieved = result["retrieved_chunks"]
        hit       = chunk_hits_at_k(retrieved, gold_ids)
        hits     += int(hit)

        # Precision@k: fraction of retrieved chunks from the correct source
        gold_sources = extract_correct_sources(gold_ids)
        correct_retrieved = sum(
            1 for c in retrieved
            if c["metadata"].get("doc_id_prefix", "") in gold_sources
        )
        precision_k = correct_retrieved / len(retrieved) if retrieved else 0.0
        total_precis += precision_k

        # Per-category tracking
        category_hits.setdefault(category, []).append(hit)

        # Print first 10 answers for manual inspection
        if verbose and i < 10:
            print(f"\n[{i+1}] {question}")
            print(f"  Hit: {'✓' if hit else '✗'}  Precision@{k}: {precision_k:.2f}  "
                  f"Latency: {latency:.1f}s")
            print(f"  Answer: {result['answer'][:200]}…")
            print(f"  Sources: {result['sources'][:3]}")

    n = len(gold)
    hit_rate   = hits / n
    avg_precis = total_precis / n
    avg_lat    = statistics.mean(latencies)

    print(f"\n{'─'*65}")
    print(f"Results  (n={n}, strategy={strategy}, k={k})")
    print(f"  Hit@{k}:          {hit_rate:.3f}  ({hits}/{n})")
    print(f"  Precision@{k}:    {avg_precis:.3f}")
    print(f"  Mean latency:   {avg_lat:.2f}s")
    print(f"\nPer-category Hit@{k}:")
    for cat, cat_hits in sorted(category_hits.items()):
        cat_rate = sum(cat_hits) / len(cat_hits)
        print(f"  {cat:<15} {cat_rate:.3f}  ({sum(cat_hits)}/{len(cat_hits)})")

    return {
        "hit_at_k":      hit_rate,
        "precision_at_k": avg_precis,
        "mean_latency":  avg_lat,
        "strategy":      strategy,
        "k":             k,
        "n":             n,
    }


# ---------------------------------------------------------------------------
# Ablation study
# ---------------------------------------------------------------------------

def run_ablation(gold: list[dict], limit: int = 20, name: str = "",
                 strategies: list[str] | None = None,
                 model: str = "claude-haiku-4-5-20251001"):
    """
    Run ablation experiments and print a summary table.

    Parameters
    ----------
    gold       : gold evaluation set
    limit      : number of questions to use (default: 20)
    name       : optional label printed in the header
    strategies : list of strategies to include, e.g. ['fixed'] or ['fixed','paragraph']
                 defaults to both ['fixed', 'paragraph']
    model      : Claude model used for answer generation across all experiments
    """
    if strategies is None:
        strategies = ["fixed", "paragraph"]

    print(f"\n{'='*65}")
    title = f"Ablation Study: {name}" if name else "Ablation Study"
    print(f"{title}  (using first {limit} questions)")
    print(f"Model: {model}  |  Strategies: {', '.join(strategies)}")
    print(f"{'='*65}")

    # Build experiment grid: all requested strategies × k=[3,5,8]
    experiments = []
    for strat in strategies:
        for k in [3, 5, 8]:
            experiments.append({
                "strategy": strat,
                "k":        k,
                "label":    f"{strat} chunks, top-{k}",
            })

    rows = []
    for exp in experiments:
        result = evaluate(gold, k=exp["k"], strategy=exp["strategy"],
                          limit=limit, verbose=False, model=model)
        rows.append((
            exp["label"],
            f"{result['hit_at_k']:.3f}",
            f"{result['precision_at_k']:.3f}",
            f"{result['mean_latency']:.1f}s",
        ))

    # Print table
    print(f"\n{'Experiment':<35} {'Hit@k':>8} {'Prec@k':>8} {'Latency':>9}")
    print("-" * 62)
    for row in rows:
        print(f"{row[0]:<35} {row[1]:>8} {row[2]:>8} {row[3]:>9}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

CLAUDE_MODELS = [
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
    "claude-opus-4-7",
]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate the Pediatric RAG pipeline.")
    parser.add_argument("--strategy", default="fixed",
                        choices=["fixed", "paragraph"],
                        help="Chunking strategy for standard eval (default: fixed)")
    parser.add_argument("--strategies", nargs="+",
                        choices=["fixed", "paragraph"],
                        help="Strategies to include in ablation (default: fixed paragraph)")
    parser.add_argument("--k",       type=int, default=5,
                        help="Number of chunks to retrieve (default: 5)")
    parser.add_argument("--model",   default="claude-haiku-4-5-20251001",
                        choices=CLAUDE_MODELS,
                        help="Claude model for answer generation (default: claude-haiku-4-5-20251001)")
    parser.add_argument("--limit",   type=int, default=None,
                        help="Limit evaluation to first N questions (default: all)")
    parser.add_argument("--ablation", action="store_true",
                        help="Run ablation study instead of standard eval")
    parser.add_argument("--name", type=str, default="",
                        help="Optional name/label for this run (e.g. 'my-run-v1')")
    args = parser.parse_args()

    gold = load_gold_set()
    print(f"Loaded {len(gold)} gold questions from {GOLD_PATH}")

    if args.ablation:
        run_ablation(gold, limit=args.limit or 20, name=args.name,
                     strategies=args.strategies, model=args.model)
    else:
        evaluate(gold, k=args.k, strategy=args.strategy,
                 limit=args.limit, model=args.model)
