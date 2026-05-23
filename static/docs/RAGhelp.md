Help — Pediatric RAG Interface












      # Interface User Guide

      This guide explains every page of the Pediatric RAG web interface — from asking your first question to running a full ablation study. The system retrieves passages from two pediatric textbooks and uses an LLM to generate grounded answers.






        🗺
        ## System Overview



      The interface has **five working pages** plus this help page. Use the navigation bar at the top to switch between them.



        [
          🔨
          #### 1. Rebuild Index

          Re-chunk the PDFs and rebuild the vector index with custom parameters.

          /build
        ](/build)
        [
          💬
          #### 2. Demo

          Ask clinical questions and see retrieved chunks + generated answers.

          /
        ](/)
        [
          📊
          #### 3. Evaluation

          Run Hit@k and Precision@k over the gold set. Label answers manually.

          /eval
        ](/eval)
        [
          🔬
          #### 4. Ablation Study

          Compare multiple configurations side-by-side. Results persist across sessions.

          /ablation
        ](/ablation)
        [
          📋
          #### 5. Gold Set Editor

          Add, edit, or delete evaluation questions. Filter by category.

          /goldset
        ](/goldset)



        **How RAG works:** When you ask a question, the system (1) embeds it with `all-MiniLM-L6-v2`, (2) finds the top-k most similar chunks via cosine similarity, (3) passes those chunks as context to the LLM, and (4) returns a grounded answer with source citations.






        🔨
        ## Rebuild Index

        Step 1 · /build


      This page re-chunks the source PDFs and rebuilds the vector index. Use it when you want to experiment with different chunk sizes or strategies.




          1

            **Choose a strategy**
            **Both** builds fixed-size and paragraph indexes simultaneously. **Fixed** or **Paragraph** builds only one. Building both takes about twice as long.



          2

            **Set chunk size and overlap**
            Drag the sliders or type values. **Chunk size**: number of characters per chunk (50–2000). **Overlap**: characters shared between adjacent chunks (0 to chunk size − 1). The live estimate shows the expected chunk count.



          3

            **Use a preset (optional)**
            Click Default (400/50), Small (300/0), Large (700/100), or Paragraph Only for common configurations.



          4

            **Click Rebuild Index**
            A live log terminal streams output from the build script. Green lines = progress. Red lines = errors. The animated progress bar fills as chunks are processed. The button re-enables when the build finishes.




      **Note:** Rebuilding replaces the current index. The Demo page's chunk popup cache is cleared automatically so it reflects the new chunks.





        💬
        ## Demo Page

        Step 2 · / (root)


      The Demo page is the main interface for testing the RAG pipeline interactively. Ask any clinical question related to pediatrics and see how the system retrieves and synthesises an answer.



        ### Asking a Question



            1

              **Type your question**
              Click the text field labelled "Ask a clinical question" and type any question. Press Enter or click **Ask ›** to submit.



            2

              **Or use a sample question**
              Click any button in the *Sample Questions* sidebar. The question is filled in and submitted automatically.



            3

              **Wait for the answer**
              The button shows a spinner. Cloud models (Claude) take 2–10 s. Local HuggingFace models may take longer on first load (model download).






        ### Controls Bar



            #### Model

            Choose the LLM that generates the answer. **Cloud models** (Haiku, Sonnet, Opus) need the Anthropic API key. **Local models** (Flan-T5, Zephyr) run on your machine — first run downloads the weights.



            #### Retrieval Strategy

            **Fixed-size** splits text into fixed-length chunks (default 400 chars). **Paragraph** splits on natural paragraph boundaries. Fixed-size is generally more consistent; paragraph better preserves meaning.



            #### Top-k Chunks

            How many chunks to retrieve and pass to the LLM. Higher k = more context but also more noise. Default is 5. Range: 1–10.






        ### Reading the Results


          | **Section** | **What it shows** |

          | **Meta badges** | Model used, strategy, latency, number of sources cited. |

          | **Generated Answer** | The LLM's answer grounded in the retrieved chunks. Bold text = emphasis. `[Source: …]` at the end cites the chunk IDs used. |

          | **Cited Sources** | Document prefixes referenced by the answer (e.g. `aap`, `kliegman`). |

          | **Retrieved Chunks** | All k chunks with their cosine similarity score shown as a bar. Higher bar = more relevant. Click the chunk ID to view the full text. |





        ### Chunk Text Popup



            1

              **Click any chunk ID**
              In the *Retrieved Chunks* section, each ID (e.g. `aap_p0248_fixed_000`) is underlined and clickable.



            2

              **A modal opens**
              Shows the full raw text of that chunk, the source document, page number, and chunk strategy.



            3

              **Close the modal**
              Click the **✕** button, click outside the modal, or press Esc.






        ### Labeling an Answer

        Below the generated answer is a *Label this answer* bar. Use it to record your human judgement:


          ✓ Correct
          ~ Partial
          ✗ Incorrect
          ⚠ Hallucinated

        Labels are saved to `eval/manual_labels.json` and also visible in the [Evaluation page](/eval) under *Saved Manual Labels*.

        **Tip:** Use **Hallucinated** when the answer states something that is not supported by any of the retrieved chunks.






        📊
        ## Evaluation Dashboard

        Step 3 · /eval


      Run a systematic evaluation of the RAG pipeline over the gold set (50 curated questions). Results stream in live as each question is processed.



        ### Running an Evaluation



            1

              **Set parameters**
              Choose strategy (Fixed / Paragraph), Top-k (1–10), number of questions to evaluate (10 for a quick test, 52 for the full set), and the model.



            2

              **Click ▶ Run Evaluation**
              A progress bar appears and per-question rows are added to the table in real time as answers come in.



            3

              **Review the summary**
              When all questions finish, the summary cards at the top fill with overall Hit@k, Precision@k, and average latency. The per-category table shows breakdown by question type.






        ### Understanding the Metrics


          | **Metric** | **Definition** | **Good value** |

          | **Hit@k**
            | Fraction of questions where at least one of the top-k retrieved chunks comes from the correct source (exact match or within ±2 pages).
            | > 75% |

          | **Precision@k**
            | Average fraction of retrieved chunks that come from the correct source document.
            | > 70% |

          | **Avg Latency**
            | Mean time (seconds) from question submission to answer received, per question.
            | < 5 s (cloud) |



        Question categories and their colour coding:


          Factual (20)
          Numerical (10)
          Temporal (5)
          Negation (8)
          Comparison (7)




        ### Manual Labeling

        Every row in the results table has label buttons. Click a button to save your judgement for that question:


          ✓ Correct
          ~ Partial
          ✗ Incorrect
          ⚠ Hallucinated

        Labels are saved immediately to `eval/manual_labels.json`. They appear in the *Saved Manual Labels* table at the bottom of this page and persist across sessions.

        **Tip:** You can re-run evaluation with different parameters and keep labeling — all previous labels are loaded automatically from disk.






        🔬
        ## Ablation Study

        Step 4 · /ablation


      Compare different retrieval configurations by running them against the gold set and recording results in a persistent table. Unlike the Evaluation page (which streams), each ablation experiment runs synchronously and saves its result to `eval/ablation_results.json`.




          1

            **Fill in the experiment form**
            Give the experiment a **Label** (e.g. "Fixed k=5 baseline"), choose Strategy, Top-k, number of questions, and model. Add optional notes to explain what you're testing.



          2

            **Or click a preset**
            Preset buttons at the bottom of the form fill in common configurations: Fixed k=5, Fixed k=3, Fixed k=10, Paragraph k=5, Paragraph k=3.



          3

            **Click ▶ Run**
            A spinner appears while the experiment runs. When finished, the result row is appended to the table. The **best Hit@k** row is highlighted in green with a BEST badge.



          4

            **Delete rows you don't need**
            Click the **✕** button on any row to remove it from the table and from disk.




      **Tip:** Start with 10–20 questions for quick comparisons, then run the best-performing configuration on all 52 questions for the final assignment report.





        📋
        ## Gold Set Editor

        Step 5 · /goldset


      The gold set is the ground-truth evaluation dataset: 50 questions with reference answers, expected chunk IDs, and category labels. This page lets you view, add, edit, and delete questions.




          1

            **Filter by category**
            Click a category button in the toolbar to show only questions of that type. Click **All** to reset.



          2

            **Add a new question**
            Click **+ Add Question** to open the edit panel. Fill in the question, reference answer, category, and (optionally) must-cite chunk IDs separated by commas. Click **Save**.



          3

            **Edit an existing question**
            Click **✏ Edit** on any row. The edit panel opens pre-filled. Change what you need and click **Save**. Changes are saved immediately to `eval/gold_set.jsonl`.



          4

            **Delete a question**
            Click **✕ Del** on a row and confirm the prompt. The question is removed from the file permanently.




      **Caution:** Deleting questions from the gold set reduces the evaluation coverage. It is better to edit an incorrect question than to delete it.

      **Must-cite chunk IDs** are the chunk IDs that a correct retrieval should include. Format: `aap_p0248_fixed_000, kliegman_p0205_fixed_003`. Used by Hit@k and Precision@k to determine correctness.






        🐍
        ## Python Files & Manual CLI

        Code Reference


      The project has **5 Python source files** plus the Flask server. Each one owns exactly one responsibility in the pipeline. Understanding which file does what lets you debug, extend, or run any stage independently from the command line.




        ### Project Layout


midRAG/
├── app.py               ← Flask web server — entry point
├── .env                 ← ANTHROPIC_API_KEY (never commit)
├── src/
│   ├── build_index.py   ← Step 1: PDF → chunks → embeddings → .npy
│   ├── retrieval.py    ← Step 2: embed query → dot product → top-k
│   ├── generation.py   ← Step 3: chunks + prompt → Claude / HF model
│   ├── rag_system.py   ← Orchestrator: retrieve → generate → answer
│   └── utils.py        ← Shared helpers (logging, path utils)
├── data/raw/            ← Source PDFs (Kliegman + AAP)
├── index/              ← Built output: *.npy + *.json
└── eval/               ← gold_set.jsonl, labels, ablation results





        ### Each File Explained






              app.py
              / (root)
              WEB SERVER


              #### Flask web server — the only entry point you need to run

              Defines all HTTP routes (`/ask`, `/build/run`, `/eval/run`, `/hf/load`, etc.), manages background threads for SSE streaming, loads `.env`, and connects the browser to the Python pipeline.

              **When to open this file:** to add a new API route, change port, or debug an HTTP error.

              python app.py






              build_index.py
              src/
              STEP 1 — BUILD


              #### PDF → chunks → embeddings → saved index + metadata

              Reads both PDFs with PyMuPDF, splits text into chunks (fixed-size sliding window or paragraph-aware), encodes every chunk with `all-MiniLM-L6-v2`, L2-normalises the vectors, saves `.npy` + `.json` to `index/`, and writes `index/index_metadata.json` (embedding model, chunk size, overlap, strategies, chunk counts, timestamp).

              **When to run manually:** when you change chunk size / overlap, add a new PDF, or the index is missing.

              --strategy fixed|paragraph|both
              --chunk-size N
              --overlap N






              retrieval.py
              src/
              STEP 2 — SEARCH


              #### Query → 384-dim vector → cosine search → top-k chunks

              Loads the pre-built `.npy` index into memory (cached after first call), embeds the query with the same sentence-transformer, computes dot-product similarity against all chunk vectors, and returns the top-k results with scores and metadata. `retrieve_hybrid()` merges both fixed and paragraph indexes and is now accessible via `answer(strategy="hybrid")`.

              **When to open this file:** to change the retrieval model, or debug why a question retrieves wrong chunks.

              retrieve(query, k=5, strategy='fixed'|'paragraph')
              retrieve_hybrid(query, k=5)  ← called automatically by answer(strategy='hybrid')






              generation.py
              src/
              STEP 3 — GENERATE


              #### Chunks + question → grounded LLM answer

              Formats retrieved chunks into a prompt with a strict system instruction (*"answer ONLY from the provided context"*), then calls either the Anthropic API (for Claude models) or loads a HuggingFace model locally. Also manages the HF model download cache and the `_hf_load_status` dict polled by the UI progress bar.

              **When to open this file:** to change the system prompt, add a new LLM backend, or fix model-loading errors.

              generate_answer(question, chunks, model, max_tokens)
              prefetch_hf_model(model_id)






              rag_system.py
              src/
              ORCHESTRATOR


              #### The complete pipeline in one function call

              Routes to `retrieve()` or `retrieve_hybrid()` based on `strategy`, then calls `generate_answer()`, extracts cited sources, and returns a structured result dict. Also times each step (`embed_retrieve_ms`, `generate_ms`) for the Pipeline Trace panel.

              **When to use directly:** quick smoke-test from terminal, or to import `answer()` into a Jupyter notebook without starting the web server.

              answer(question, k=5, strategy='fixed'|'paragraph'|'hybrid', model='...')






              utils.py
              src/
              HELPERS


              #### Shared utilities used by the other modules

              Logging setup, path resolution helpers, and other shared code. You rarely need to run or edit this file directly.









        ### Running Each Stage Manually

        Every stage can be run from the terminal without starting the web server. Open a terminal in the project root (`midRAG/`) and run the commands below.



        #### 0 — Start the web server


# Start Flask on http://localhost:5000
$ python app.py

Starting RAG demo at http://localhost:5000
 * Debug mode: on  — auto-reloads on file change



        #### 1 — Build / rebuild the vector index


# Build both strategies with default settings (400 chars, 50 overlap)
$ python src/build_index.py

# Build only fixed-size with custom chunk size
$ python src/build_index.py --strategy fixed --chunk-size 300 --overlap 30

# Build paragraph-aware index only
$ python src/build_index.py --strategy paragraph

Expected output:
[BUILD] Loading Kliegman.pdf ... 371 pages
[BUILD] Loading AAP.pdf ... 785 pages
[BUILD] Fixed chunks: 15,357  |  Embedding batch 1/240 ...
[BUILD] Saved index/fixed_embeddings.npy  (15357, 384)
[BUILD] Done in 94s



        #### 2 — Test retrieval alone


$ python -c "
from src.retrieval import retrieve
results = retrieve('febrile seizure discharge criteria', k=3, strategy='fixed')
for r in results:
    print(r['chunk_id'], round(r['score'],3), r['text'][:80])
"

Expected output:
aap_p0051_fixed_000  0.891  Febrile seizures typically occur in children aged...
klieg_p0334_fixed_002  0.867  The discharge criteria for febrile seizure include...
aap_p0052_fixed_001  0.845  Parents should be counselled that simple febrile...



        #### 3 — Test the full RAG pipeline


# rag_system.py has a built-in demo when run as __main__
$ python src/rag_system.py

Expected output:
Q: What are the discharge criteria for a child with febrile seizure?
A: According to the retrieved sources, discharge criteria include...
   [Source: aap_p0051_fixed_000, klieg_p0334_fixed_002]
Sources: ['aap_p0051_fixed_000', 'klieg_p0334_fixed_002']

# Or call answer() directly in Python
$ python -c "
from src.rag_system import answer
r = answer('What causes febrile seizures?', k=5)
print(r['answer'])
print('Sources:', r['sources'])
print('Timings:', r['_timings'])
"



        #### 4 — Test generation alone (Claude)


# generation.py has a smoke test when run as __main__ (needs ANTHROPIC_API_KEY)
$ python src/generation.py

# Or call generate_answer() with fake chunks to test the prompt format
$ python -c "
from src.generation import generate_answer
chunks = [{'chunk_id':'test_001','text':'Febrile seizures occur in 2-5% of children.','score':0.9,'metadata':{'source':'aap','page':51}}]
print(generate_answer('What is the incidence of febrile seizures?', chunks))
"



        #### 5 — Pre-download a HuggingFace model


# Download Flan-T5 Base (~300 MB) to local HuggingFace cache
$ python -c "
from src.generation import prefetch_hf_model, _hf_load_status
prefetch_hf_model('google/flan-t5-base')
print(_hf_load_status)
"

Expected output:
{'google/flan-t5-base': {'state': 'ready', 'progress': 100, 'detail': 'Model loaded and ready'}}



          **Tip — run order for a clean start:**

            - Make sure `.env` has a valid `ANTHROPIC_API_KEY`

            - `python src/build_index.py` — builds the index (only needed once, or after adding PDFs)

            - `python src/rag_system.py` — sanity-check: confirms retrieve + generate work end-to-end

            - `python app.py` — starts the web server; open `http://localhost:5000`





          **Important:** Always run from the *project root* (`midRAG/`), not from inside `src/`. The `.env` file and the `index/` folder are resolved relative to `app.py`'s location.








        ⚡
        ## Quick Reference




        | **Keyboard shortcut** | **Action** |

        | Enter | Submit question (Demo page) |

        | Esc | Close chunk popup modal |




        | **File** | **Purpose** |

        | `eval/gold_set.jsonl` | Gold evaluation questions (one JSON object per line) |

        | `eval/manual_labels.json` | Human labels saved from Demo and Eval pages |

        | `eval/ablation_results.json` | Persistent ablation experiment results |

        | `index/fixed_chunks.json` | Fixed-size chunk metadata (text + page + source) |

        | `index/paragraph_chunks.json` | Paragraph chunk metadata |

        | `index/fixed_embeddings.npy` | Fixed-size embedding matrix (numpy) |

        | `index/paragraph_embeddings.npy` | Paragraph embedding matrix (numpy) |

        | `.env` | API keys — contains `ANTHROPIC_API_KEY` |

        | `runCMD.ps1` | PowerShell script to start the server correctly |




        | **Chunk ID format** | **Meaning** |

        | `aap_p0248_fixed_000` | **aap** = document · **p0248** = page 248 · **fixed** = strategy · **000** = chunk index on that page |

        | `kliegman_p0205_paragraph_003` | **kliegman** = document · **p0205** = page 205 · **paragraph** = strategy · **003** = index |




        **Starting the server:** Always use `.\runCMD.ps1` from the project folder. It loads the API key from `.env` and starts Flask with proper UTF-8 encoding.







        🔧
        ## Troubleshooting & Common Errors

        Fixes


      Match your error to a block below. Each entry describes the cause, how to confirm it, and the exact fix.





          ERROR
          #### [WinError 22] Invalid argument — or — [Errno 22] Invalid argument



          Appears in the terminal or in the UI when the HuggingFace Hub tries to create symbolic links inside `~/.cache/huggingface/hub/`. Windows blocks symlink creation unless Developer Mode is enabled.

          **Root cause:** HuggingFace Hub's default cache stores model files as blobs and creates symlinks from the snapshots folder pointing to them. Windows refuses to create symlinks without elevated privileges.
          **Fix (already applied):** The app uses `snapshot_download(local_dir=..., local_dir_use_symlinks=False)` which downloads files directly to `model_cache/` without any symlinks.
If you still see this error, make sure you are running the latest `generation.py` from this project — older versions used `hf_hub_download()` which hits the same issue.
          You can also enable Windows Developer Mode (*Settings → System → For developers → Developer Mode*) to permanently allow symlinks for your account, but it is not required.







          ERROR
          #### EnvironmentError: ANTHROPIC_API_KEY environment variable is not set



          The `/ask` endpoint tried to call the Anthropic API but could not find the key.

          **Root cause:** The `.env` file is missing, the key name is misspelled, or the server was started without loading `.env` first.

            **Fix 1 — Use runCMD.ps1 (recommended):**

            Run `.\runCMD.ps1` from the project root. This script loads `.env` and starts Flask with correct encoding.


            **Fix 2 — Create / check the .env file:**

            Create a file named `.env` in the project root (same folder as `app.py`) with exactly:

            `ANTHROPIC_API_KEY=sk-ant-api03-...`

            No quotes, no spaces around `=`.

          **Never** commit `.env` to git — it contains your secret API key.






          ERROR
          #### FileNotFoundError: index/fixed_embeddings.npy — or — KeyError loading chunks



          The retrieval layer tried to load the vector index but the files do not exist yet.

          **Root cause:** `build_index.py` has never been run, or the `index/` folder was deleted.

            **Fix:** Build the index from the Rebuild page ([/build](/build)), or run from the terminal:

            `python src/build_index.py`

            This creates `index/fixed_embeddings.npy`, `index/fixed_chunks.json`, and their paragraph equivalents. Takes ~90 seconds on CPU for both PDFs.

          Also verify the two PDFs are present in `data/raw/` — the build script will fail silently if neither PDF is found, producing an empty index.







          WARN
          #### HuggingFace model stuck at "downloading 10%", or shows "error" badge



          The background download thread hit a problem. Possible causes:


            **Cause A — Slow connection:** Large models (Flan-T5 Base ≈ 300 MB, Zephyr-7B ≈ 14 GB) can take 5–45 minutes on a standard connection. The progress bar shows only discrete steps (10% → 75% → 80% → 100%) — it will appear frozen between steps.


            **Cause B — Network error during download:** The HuggingFace Hub may time out or throttle. Check the server terminal for a traceback.


            **Cause C — Transformers / accelerate not installed:** Local models require `pip install transformers accelerate` (these are commented out in `requirements.txt` as optional).


            **Fix A:** Wait. For Flan-T5 Base, allow 5–15 minutes. Refresh the status badge periodically.

            **Fix B:** Click the model's Download button again — it will resume from scratch. Or pre-download in the terminal:

            `python -c "from src.generation import prefetch_hf_model; prefetch_hf_model('google/flan-t5-base')"`

            **Fix C:** Run `pip install transformers accelerate huggingface_hub` then restart the server.







          ERROR
          #### HTTP 500 Internal Server Error on /ask — or — answer panel shows "Error"



          The server raised an unhandled exception while processing a question. Check the **terminal** where you started Flask — the full Python traceback is printed there.

          **Most common causes:** (1) Index not built → FileNotFoundError. (2) API key missing → EnvironmentError. (3) Anthropic API rate limit or network timeout → anthropic.APIStatusError. (4) Corrupted or empty `.npy` file.

            **Step-by-step diagnosis:**

            1. Read the traceback in the terminal — the last line names the exception type.

            2. If FileNotFoundError → build the index (see above).

            3. If EnvironmentError → set ANTHROPIC_API_KEY (see above).

            4. If anthropic.RateLimitError → wait 60 seconds and retry.

            5. If numpy error → delete `index/` and rebuild.







          INFO
          #### Answer says: "The information was not found in the provided sources"



          This is **not an error** — it is the intended fallback behaviour when none of the retrieved chunks contain enough information to answer the question.

          **Why it happens:** The system prompt instructs the LLM to say this phrase instead of guessing. It triggers when: (a) the answer is genuinely not in the corpus, (b) the retrieval brought back irrelevant chunks, or (c) the question requires multi-hop reasoning across chunks that were not all retrieved.

            **Improve recall by:**

            • Increasing Top-k (e.g. from 5 to 8) — gives the LLM more context.

            • Switching strategies (paragraph often works better for narrative Q&A; fixed for decision trees).

            • Rephrasing the question — use clinical terminology matching the books' vocabulary.

            • Checking whether the topic is in the corpus at all (Kliegman = decision trees; AAP = 50 named cases).










        🏗
        ## Architecture Deep Dive

        How It Works


      The RAG pipeline has five distinct stages. Each stage is isolated in its own Python file, which makes it easy to swap components or debug individual steps without touching the rest of the system.




        ### The 5-Step Pipeline






              1



              #### Index Build — `build_index.py`

              Run once (or whenever you change chunking parameters). Loads both PDFs with PyMuPDF, splits text into chunks using the selected strategy, encodes every chunk with the sentence-transformer, L2-normalises the vectors, and saves two files per strategy.


                Output: `index/fixed_embeddings.npy` (shape N×384, float32) + `index/fixed_chunks.json` (list of metadata dicts).

                Chunking strategies: **Fixed-size** (sliding window, default 400 chars / 50 overlap) vs **Paragraph-aware** (split on double-newlines, 100–700 char range).

                ~15,000 chunks for both books combined; embedding takes ~90 s on CPU.






              2



              #### Query Embedding — `retrieval.py`

              At query time, the same sentence-transformer encodes the user's question into a 384-dimensional vector, then L2-normalises it.


                Model: `sentence-transformers/all-MiniLM-L6-v2` — 22 MB, 384 dim, CPU-friendly (~20 ms per query).

                The model is cached in memory after the first call so subsequent queries pay no reload cost.






              3



              #### Cosine Search — `retrieval.py`

              The query vector is dot-producted against every row of the embedding matrix in a single NumPy operation. Because all vectors are L2-normalised, the dot product equals cosine similarity. The top-k indices are returned with their scores.


                Implementation: `scores = embeddings @ qvec  →  np.argpartition(scores, -k)[-k:]`

                Flat index: O(n) per query. For n=15,000 and 384 dims this takes <1 ms on any modern CPU — no approximate nearest-neighbour library (FAISS / HNSW) needed at this scale.






              4



              #### Grounded Generation — `generation.py`

              The top-k chunks are formatted into a context block and injected into a structured prompt sent to the LLM (Anthropic Claude or a local HuggingFace model). The LLM is instructed to answer *only* from the provided context and to cite chunk IDs.


                Default model: `claude-haiku-4-5-20251001` — fast, cost-efficient (~2–4 s, ~$0.0004 per query).

                Higher quality option: `claude-sonnet-4-6` (change `MODEL` in generation.py or select in the UI).

                Local option: `google/flan-t5-base` (~300 MB, ~30 s on CPU) for offline / private use.






              ✓


              #### Structured Result — `rag_system.py`

              The orchestrator packages the answer, cited source IDs, and full chunk objects (with scores) into a JSON-serialisable dict. Timing data for each sub-step is included for the Pipeline Trace panel in the UI.


                Return shape: `{"answer": "…[Source: chunk_id]", "sources": [...], "retrieved_chunks": [...], "_timings": {"embed_retrieve_ms": N, "generate_ms": N}}`









        ### Prompt Structure

        Every call to the Anthropic API uses the following structure. Understanding the prompt explains most of the system's behaviour.



── SYSTEM PROMPT (constant) ────────────────────────────
You are a pediatric medicine question-answering assistant.
Answer questions using ONLY the provided context passages.
Rules:
1. Base your answer strictly on the retrieved context.
2. If the answer is not found in the context, say:
   "The information was not found in the provided sources."
3. After your answer, always cite the chunk IDs you relied on,
   like: [Source: chunk_id_1, chunk_id_2]
4. Be concise and clinically precise. Do not add information
   from general knowledge.

── USER MESSAGE (built per query) ──────────────────────
Question:
{the user's question}

Context:
[aap_p0251_fixed_000] (source: AAP_Case-Based.pdf, page 251)
{chunk text …}

---

[kliegman_p0152_fixed_002] (source: Kliegman.pdf, page 152)
{chunk text …}

  … up to k chunks, each separated by --- …

Answer:



          **Why strict grounding matters:** Without rule #4, Claude would draw on its medical training knowledge and generate fluent but potentially wrong or hallucinated answers. The prompt forces it to treat the retrieval results as the only valid information source — making the citation honest and the "not found" fallback meaningful.



          | **Prompt component** | **Controlled by** | **Change it in** |

          | System instruction text | `SYSTEM_PROMPT` constant | `src/generation.py` line 30 |

          | Max answer length | `MAX_TOKENS = 512` | `src/generation.py` line 28 |

          | Context format (chunk layout) | `_format_context()` | `src/generation.py` line 40 |

          | Model used | `MODEL` constant or UI dropdown | UI → Controls bar, or `generation.py` line 27 |

          | Number of chunks passed | Top-k slider | UI → Controls bar (1–10) |










        ❓
        ## Frequently Asked Questions

        FAQ





          QWhy does the answer sometimes say "The information was not found in the provided sources" even for a reasonable question?
          This happens when the retrieved chunks don't contain the answer — either because the topic isn't in the corpus, the question phrasing doesn't match the book's vocabulary, or the relevant passage was ranked below position k. Try: increasing Top-k, switching strategy (Fixed ↔ Paragraph), or rephrasing with clinical terminology. It can also happen with multi-part questions that require information from two different sections of the books.



          QCan I add my own PDF to the corpus?
          Yes. Place the PDF in `data/raw/`, then open `src/build_index.py` and add a line to the `PDF_FILES` list (or equivalent config at the top of the file). Then rebuild the index via the Rebuild page or `python src/build_index.py`. Chunk IDs will be prefixed with a slug derived from the filename.



          QHow long does rebuilding the index take?
          About **90–120 seconds** on a modern laptop CPU for both PDFs together (~15,000 chunks, 384-dim embeddings). Building only one strategy takes roughly half that. The Rebuild page shows a live log with per-batch progress. The embedding model (`all-MiniLM-L6-v2`) is cached after the first load, so subsequent rebuilds are faster to start.



          QWhat is the difference between Fixed-size and Paragraph chunking?
          **Fixed-size** splits text into overlapping windows of a fixed character count (default 400 chars, 50 overlap). Every chunk is roughly the same length, which makes the embedding space uniform. It works well for the Kliegman decision-tree pages where paragraphs are short and dense. **Paragraph-aware** splits on double-newlines and keeps natural paragraph boundaries intact. Chunks vary in length (100–700 chars) but preserve narrative context. It works better for the AAP case-based Q&A sections where multi-sentence paragraphs contain a complete thought. The ablation study lets you compare their Hit@k side-by-side.



          QWhy is the local HuggingFace model so slow?
          Local models run on CPU by default. Flan-T5 Base takes **30–90 seconds** per query on a typical laptop CPU. Zephyr-7B takes several minutes. This is a fundamental hardware limitation — GPUs are 50–100× faster for transformer inference. The models are useful when you need an offline / private pipeline, but for speed, the Claude API is always preferable. If you have an NVIDIA GPU, `accelerate` will automatically use it (`device_map="auto"` in the pipeline call).



          QCan I use GPT-4 or Gemini instead of Claude?
          Not out of the box, but the architecture makes it easy. `generate_answer()` in `generation.py` routes on the model name string: anything starting with `"claude-"` goes to the Anthropic backend; everything else currently goes to the HuggingFace backend. To add OpenAI, add an `elif model.startswith("gpt-")` branch that calls the `openai` package, and expose it in the UI dropdown in `app.py`. The prompt format (system + user + context) is identical across providers.



          QWhat does the ±2 page tolerance in Hit@k mean?
          When we check whether a retrieved chunk "hit" the correct source, we allow the page number to be off by up to 2 pages in either direction. This accounts for: (a) differences between PDF page numbers and the book's printed page numbers (cover pages, introductions), (b) content that spans a page break and lands in a chunk from an adjacent page, and (c) minor imprecision in our gold set annotations. A hit is counted if *any* of the top-k retrieved chunks is within ±2 pages of the expected answer page in the correct document.



          QHow do I completely reset the system to a clean state?

            Delete these generated files, then rebuild:

            `del index\*.npy index\*.json`
            `del eval\ablation_results.json`
            `# Keep eval\gold_set.jsonl and eval\manual_labels.json unless you also want to reset those`
            Then run `python src/build_index.py` to regenerate the index. The model cache (`model_cache/`) can also be deleted to force re-download of HuggingFace weights.




          QWhy does the pipeline trace panel show two separate timings?
          The timings distinguish the two slowest steps: **embed + retrieve** (embedding the query + cosine search, typically <200 ms) and **generate** (LLM API call, typically 2–8 s for Claude). Separating them lets you see whether latency is a retrieval problem (index too large, model loading) or a generation problem (slow API, long answer, high max_tokens). Local HF models will show generate times in the 30–120 s range.



          QCan I run the evaluation without the web UI?
          Yes — `eval/run_eval.py` is a standalone script. Run it from the project root:

          `python eval/run_eval.py` for the standard evaluation, or

          `python eval/run_eval.py --ablation` for the full ablation table.

          Results are printed to stdout and also saved to `eval/ablation_results.json` so they appear in the web UI when you start the server.








        📥
        ## Downloads

        Project Files


      All key project documents are available for direct download below.




        [
          📋

            **Mid-Term Assignment**
            Original assignment specification (PDF)

          PDF
        ](/static/docs/mid_term_assignment.pdf)

        [
          📄

            **Project Report**
            Full written report with methodology & results (PDF)

          PDF
        ](/static/docs/report.pdf)

        [
          📖

            **README**
            Quick-start guide, architecture overview & API reference

          MD
        ](/static/docs/README.md)

        [
          📚

            **Corpus Manifest**
            Dataset description, sources, licensing & question types

          MD
        ](/static/docs/MANIFEST.md)

        [
          📦

            **requirements.txt**
            Python dependencies — install with `pip install -r requirements.txt`

          TXT
        ](/static/docs/requirements.txt)