# Pediatric RAG Pipeline

A **Retrieval-Augmented Generation (RAG)** system over two pediatric medicine textbooks, built for the Mid-Course RAG Assignment.

## Corpus

| Book | Pages | Structure |
|---|---|---|
| Kliegman – Pediatric Decision-Making Strategies (2015) | 371 | Symptom-based decision trees |
| AAP – Pediatric Hospital Medicine: A Case-Based Guide (2022) | 785 | 50+ named patient cases in Q&A format |

## Project Structure

```
project/
├── data/
│   ├── raw/               ← place the two PDFs here before running
│   ├── processed/         ← auto-generated: chunked JSONL files
│   └── MANIFEST.md
├── src/
│   ├── utils.py           ← PDF loading, text cleaning, chunking
│   ├── build_index.py     ← chunk → embed → numpy index
│   ├── retrieval.py       ← retrieve(query, k, strategy)
│   ├── generation.py      ← Claude-based answer generation
│   └── rag_system.py      ← answer(question) – main public API
├── eval/
│   ├── gold_set.jsonl     ← 50 evaluation questions
│   └── run_eval.py        ← Hit@k, Precision@k, ablation table
├── index/                 ← auto-generated numpy index (.npy + .json)
├── report.pdf
├── requirements.txt
└── README.md
```

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Place PDFs in `data/raw/`
```
data/raw/Kliegman_Pediatric Decision-Making Strategies_2015.pdf
data/raw/A Case-Based Educational Guide-American Academy of Pediatrics (2022).pdf
```

### 3. Build the vector index
```bash
python src/build_index.py
```
This loads both PDFs, applies **two chunking strategies** (fixed-size and paragraph-aware), embeds all chunks with `sentence-transformers/all-MiniLM-L6-v2`, and saves two numpy index pairs (`fixed_embeddings.npy` + `fixed_chunks.json`, same for `paragraph`) to `index/`.

To experiment with different chunk sizes:
```bash
python src/build_index.py --strategy fixed --chunk-size 300
python src/build_index.py --strategy fixed --chunk-size 700
```

### 4. Set your Anthropic API key
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### 5. Run evaluation
```bash
python eval/run_eval.py
```

Run the ablation study:
```bash
python eval/run_eval.py --ablation
```

---

## Public API

```python
from src.rag_system import answer

result = answer("What are the discharge criteria for febrile seizure?")

print(result["answer"])           # natural-language answer with inline citations
print(result["sources"])          # list of chunk IDs cited
print(result["retrieved_chunks"]) # full chunk objects with score and metadata
```

Return format:
```json
{
  "answer": "The patient has returned to baseline neurologic status...\n[Source: aap_p0251_fixed_000]",
  "sources": ["aap_p0251_fixed_000"],
  "retrieved_chunks": [
    {
      "chunk_id": "aap_p0251_fixed_000",
      "text": "...",
      "score": 0.87,
      "metadata": {"source": "AAP_Case-Based.pdf", "page": 251, "section": "Case 16: Simon..."}
    }
  ]
}
```

---

## System Architecture

```
Question
   │
   ▼
SentenceTransformer("all-MiniLM-L6-v2")
   │  query embedding (384-dim, L2-normalised)
   ▼
NumPy cosine search (embeddings @ qvec.T)
   │  top-k chunks
   ▼
Anthropic Claude (claude-haiku-4-5)
   │  grounded generation with source citation rule
   ▼
answer() → {answer, sources, retrieved_chunks}
```

### Chunking Strategies

| Strategy | Chunk size | Overlap | When it helps |
|---|---|---|---|
| **Fixed-size** | 400 chars | 50 chars | Kliegman decision-tree pages (dense, short) |
| **Paragraph-aware** | 100–700 chars | none | AAP narrative Q&A paragraphs |

### Embedding Model

`all-MiniLM-L6-v2` — 384-dimensional, fast (CPU-friendly), strong semantic retrieval for English medical text.

### Vector Index

Plain **NumPy** flat index — embeddings saved as `index/fixed_embeddings.npy` (float32, shape N×384) alongside `index/fixed_chunks.json` metadata. Cosine similarity computed as a single matrix multiply (`embeddings @ qvec.T`) on L2-normalised vectors. Fully reproducible: re-running `build_index.py` overwrites the files from scratch. No external vector database required.

---

## Evaluation

The `eval/gold_set.jsonl` contains **50 questions** across five categories:

| Category | Count |
|---|---|
| Factual | 20 |
| Numerical | 10 |
| Temporal | 5 |
| Negation / absence | 8 |
| Comparison | 7 |

**Metrics:**
- **Hit@k** – fraction of questions where at least one gold source page appears in top-k (soft ±2 page match)
- **Precision@k** – fraction of retrieved chunks from the correct source
- Manual answer quality for first 10 results (Correct / Partially correct / Incorrect / Hallucinated)

---

## Notes

- The system will say *"The information was not found in the provided sources"* when the answer is not in the retrieved context.
- All answers include an inline `[Source: chunk_id, ...]` citation.
- The pipeline is framework-aware but not a black box: every component (`utils.py`, `retrieval.py`, `generation.py`) is under 200 lines and can be read and modified independently.
