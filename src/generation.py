"""
generation.py  –  LLM-based answer generation.

Supports two backends:
  - Anthropic Claude (cloud)  — any model whose ID starts with "claude-"
  - HuggingFace Transformers  — any other model ID (loaded locally)

Public API:
    generate_answer(question, retrieved_chunks, model, max_tokens) -> str
"""

import os
import sys
import time
from pathlib import Path
import anthropic
from dotenv import load_dotenv

# Load .env from project root regardless of where the script is run from
load_dotenv(Path(__file__).parent.parent / ".env")

# Local model cache — avoids Windows symlink errors ([Errno 22]) that occur
# when huggingface_hub tries to create symlinks in ~/.cache/huggingface/hub/
_PROJECT_ROOT  = Path(__file__).parent.parent
_MODEL_CACHE   = _PROJECT_ROOT / "model_cache"
_MODEL_CACHE.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL      = "claude-haiku-4-5-20251001"   # fast, cost-efficient; swap for claude-sonnet-4-6 for higher quality
MAX_TOKENS = 512

SYSTEM_PROMPT = """You are a pediatric medicine question-answering assistant.
Answer questions using ONLY the provided context passages.
Rules:
1. Base your answer strictly on the retrieved context.
2. If the answer is not found in the context, say: "The information was not found in the provided sources."
3. After your answer, always cite the chunk IDs you relied on, like: [Source: chunk_id_1, chunk_id_2]
4. Be concise and clinically precise. Do not add information from general knowledge.
"""


def _format_context(retrieved_chunks: list[dict]) -> str:
    """
    Format a list of retrieved chunks into a structured context block for the LLM prompt.

    Each chunk is rendered as a labelled block containing its chunk ID, source file,
    page number, and text. Blocks are separated by '---' dividers so the model can
    clearly distinguish where one chunk ends and the next begins.

    Example output:
        [aap_p0251_fixed_000] (source: AAP_Case-Based.pdf, page 251)
        The patient has returned to baseline neurologic status...

        ---

        [kliegman_p0032_fixed_001] (source: Kliegman_Pediatric.pdf, page 32)
        Febrile seizures affect 2-5% of children aged 6 months to 5 years...

    Parameters
    ----------
    retrieved_chunks : list[dict]
        Chunk objects returned by retrieve(), each containing:
        'chunk_id', 'text', 'score', 'metadata' (with 'source' and 'page').

    Returns
    -------
    str
        Multi-line context string ready to be inserted into the LLM user message.
    """
    parts = []
    for chunk in retrieved_chunks:
        cid    = chunk.get("chunk_id", "unknown")
        source = chunk.get("metadata", {}).get("source", "")
        page   = chunk.get("metadata", {}).get("page", "")
        text   = chunk.get("text", "")
        parts.append(
            f"[{cid}] (source: {source}, page {page})\n{text}"
        )
    return "\n\n---\n\n".join(parts)


def generate_answer(question: str,
                    retrieved_chunks: list[dict],
                    model: str = MODEL,
                    max_tokens: int = MAX_TOKENS) -> str:
    """
    Generate a grounded answer to a question using the retrieved context chunks.

    Routes automatically to the correct backend based on the model name:
    - Model IDs starting with 'claude-' → Anthropic API (_generate_anthropic)
    - Any other model ID → Local HuggingFace Transformers (_generate_hf)

    The answer is grounded strictly in the retrieved_chunks context — the system
    prompt instructs the model not to use outside knowledge and to always cite
    the chunk IDs it relied on using [Source: chunk_id_1, chunk_id_2] syntax.

    Parameters
    ----------
    question         : str
        The user's natural-language question.
    retrieved_chunks : list[dict]
        Chunks returned by retrieve() — used as the grounding context.
    model            : str
        Model identifier. Default: 'claude-haiku-4-5-20251001'.
    max_tokens       : int
        Maximum tokens in the generated answer. Default: 512.

    Returns
    -------
    str
        Generated answer text, ending with a [Source: ...] citation block.
    """
    if model.startswith("claude-"):
        return _generate_anthropic(question, retrieved_chunks, model, max_tokens)
    return _generate_hf(question, retrieved_chunks, model, max_tokens)


# ── Anthropic backend ──────────────────────────────────────────────────────────

def _generate_anthropic(question: str,
                         retrieved_chunks: list[dict],
                         model: str,
                         max_tokens: int) -> str:
    """
    Call the Anthropic Claude API to generate a grounded answer.

    Builds a two-part prompt:
    - System: grounding rules (answer only from context, cite sources, say 'not found' if missing)
    - User: the question + formatted context block from _format_context()

    Retries automatically up to 8 times with exponential backoff (capped at 60s)
    when the API returns HTTP 529 (overloaded). Raises immediately on all other errors.

    Parameters
    ----------
    question         : str
        The user's question.
    retrieved_chunks : list[dict]
        Context chunks to ground the answer in.
    model            : str
        Anthropic model ID (e.g. 'claude-haiku-4-5-20251001').
    max_tokens       : int
        Maximum tokens to generate.

    Returns
    -------
    str
        Raw text response from the model, stripped of leading/trailing whitespace.

    Raises
    ------
    EnvironmentError
        If ANTHROPIC_API_KEY is not set in the environment.
    anthropic.APIStatusError
        If the API returns a non-529 error, or if all 8 retry attempts fail.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Export it before running:\n  export ANTHROPIC_API_KEY=sk-ant-..."
        )

    client  = anthropic.Anthropic(api_key=api_key)
    context = _format_context(retrieved_chunks)

    user_message = (
        f"Question:\n{question}\n\n"
        f"Context:\n{context}\n\n"
        f"Answer:"
    )

    # Retry up to 8 times on overload (529) with exponential backoff
    for attempt in range(8):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            return response.content[0].text.strip()
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and attempt < 7:
                wait = min(2 ** attempt, 60)  # 1,2,4,8,16,32,60,60s
                print(f"  ⚠️  API overloaded — retrying in {wait}s... (attempt {attempt+1}/8)")
                time.sleep(wait)
            else:
                raise


# ── HuggingFace local backend ──────────────────────────────────────────────────

# Model cache: stores either
#   ("seq2seq", tokenizer, model)   — for Flan-T5 / BART encoder-decoder models
#   ("causal",  pipeline_obj)       — for decoder-only models (Zephyr, Mistral …)
_hf_pipelines: dict = {}

# Download/load status — polled by the UI via GET /hf/status.
# Each value is a dict:
#   {"state": "idle"|"downloading"|"loading"|"ready"|"error",
#    "progress": 0-100,
#    "detail":   "human-readable current activity"}
_hf_load_status: dict = {}

# Models known to be encoder-decoder (text2text); everything else is treated as
# a causal decoder model.
_SEQ2SEQ_PREFIXES = ("google/flan-t5", "google/t5", "facebook/bart")


def _is_seq2seq(model_id: str) -> bool:
    return any(model_id.startswith(p) for p in _SEQ2SEQ_PREFIXES)


def prefetch_hf_model(model_id: str) -> None:
    """Download all model files then load into memory.

    Uses snapshot_download (more robust than per-file downloads — handles
    retries internally and avoids Windows symlink errors via local_dir).
    Designed to run inside a background thread.
    Updates _hf_load_status throughout so the UI can show a live progress bar.
    """
    if model_id in _hf_pipelines:
        _hf_load_status[model_id] = {"state": "ready", "progress": 100,
                                      "detail": "Model already loaded"}
        return

    # Guard against double-start
    cur = _hf_load_status.get(model_id, {})
    if isinstance(cur, dict) and cur.get("state") in ("downloading", "loading"):
        return

    _hf_load_status[model_id] = {"state": "downloading", "progress": 0,
                                  "detail": "Connecting to HuggingFace Hub…"}
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        _hf_load_status[model_id] = {"state": "error", "progress": 0,
                                      "detail": "Run: pip install huggingface_hub transformers accelerate"}
        return

    # Local dir for this model — no symlinks (fixes [Errno 22] on Windows)
    local_dir = _MODEL_CACHE / model_id.replace("/", "--")
    local_dir.mkdir(parents=True, exist_ok=True)

    # ── Phase 1: download via snapshot_download (no symlinks → no [Errno 22]) ──
    _hf_load_status[model_id] = {"state": "downloading", "progress": 10,
                                  "detail": "Downloading model files (this may take a few minutes)…"}
    try:
        # local_dir_use_symlinks=False avoids [Errno 22] "Invalid argument" on Windows
        snapshot_download(
            repo_id=model_id,
            local_dir=str(local_dir),
            local_dir_use_symlinks=False,
            ignore_patterns=["*.md", "*.txt", "README*", "LICENSE*",
                             "*.png", "*.jpg", "*.jpeg", "*.gif", "*.svg",
                             ".gitattributes"],
        )
    except TypeError:
        # Older huggingface_hub — retry without local_dir_use_symlinks kwarg
        try:
            snapshot_download(
                repo_id=model_id,
                local_dir=str(local_dir),
                ignore_patterns=["*.md", "*.txt", "README*", "LICENSE*",
                                 "*.png", "*.jpg", "*.jpeg", "*.gif", "*.svg",
                                 ".gitattributes"],
            )
        except Exception as exc:
            _hf_load_status[model_id] = {"state": "error", "progress": 0,
                                          "detail": f"Download failed: {exc}"}
            return
    except Exception as exc:
        _hf_load_status[model_id] = {"state": "error", "progress": 0,
                                      "detail": f"Download failed: {exc}"}
        return

    _hf_load_status[model_id] = {"state": "downloading", "progress": 75,
                                  "detail": "Download complete — preparing to load…"}

    # ── Phase 2: load weights into memory ────────────────────────────────────
    _hf_load_status[model_id] = {"state": "loading", "progress": 80,
                                  "detail": "Loading model weights into memory…"}
    try:
        _get_hf_pipeline(model_id)   # sets "ready" on success; "error" on failure
    except Exception:
        pass   # _get_hf_pipeline already wrote the error state


def _get_hf_pipeline(model_id: str):
    """Load (or return cached) a HuggingFace model for model_id.

    Seq2seq models (Flan-T5, BART) are loaded via AutoModelForSeq2SeqLM +
    AutoTokenizer to avoid the 'text2text-generation' task string removed
    in newer transformers versions (≥ 4.40).

    Returns a tuple:
        ("seq2seq", tokenizer, model)   for encoder-decoder models
        ("causal",  pipeline_obj)       for causal decoder models
    """
    if model_id not in _hf_pipelines:
        try:
            from transformers import (AutoTokenizer, AutoModelForSeq2SeqLM,
                                      pipeline)
        except ImportError:
            raise ImportError(
                "The 'transformers' package is required for local HuggingFace models. "
                "Install it with:  pip install transformers accelerate"
            )

        # Don't overwrite "loading" state set by prefetch_hf_model — that means
        # files are already downloaded and we are just doing the torch.load step.
        cur = _hf_load_status.get(model_id, {})
        if not (isinstance(cur, dict) and cur.get("state") == "loading"):
            _hf_load_status[model_id] = {"state": "downloading", "progress": 5,
                                          "detail": f"Downloading / loading '{model_id}'…"}

        # Resolve load path: prefer local cache (avoids symlink issues on Windows)
        local_dir = _MODEL_CACHE / model_id.replace("/", "--")
        load_path = str(local_dir) if local_dir.exists() and any(local_dir.iterdir()) else model_id

        print(f"[HF] Loading '{model_id}' from {load_path} …")
        try:
            if _is_seq2seq(model_id):
                tokenizer = AutoTokenizer.from_pretrained(load_path)
                model     = AutoModelForSeq2SeqLM.from_pretrained(load_path)
                _hf_pipelines[model_id] = ("seq2seq", tokenizer, model)
            else:
                _hf_pipelines[model_id] = ("causal", pipeline(
                    "text-generation",
                    model=load_path,
                    device_map="auto",
                    trust_remote_code=False,
                ))
            _hf_load_status[model_id] = {"state": "ready", "progress": 100,
                                          "detail": "Model loaded and ready"}
            print(f"[HF] Model '{model_id}' ready.")
        except Exception as exc:
            _hf_load_status[model_id] = {"state": "error", "progress": 0,
                                          "detail": str(exc)}
            raise

    return _hf_pipelines[model_id]


def _generate_hf(question: str,
                  retrieved_chunks: list[dict],
                  model_id: str,
                  max_tokens: int) -> str:
    """
    Run inference with a locally loaded HuggingFace model.

    Supports two model architectures detected automatically:
    - Encoder-decoder (seq2seq) models like Flan-T5 / BART:
      Uses AutoTokenizer + AutoModelForSeq2SeqLM → model.generate() → decode.
    - Causal decoder-only models like Zephyr / Mistral-Instruct:
      Uses a text-generation pipeline with chat-template if available,
      falling back to a plain string prompt.

    The model must have been pre-loaded via prefetch_hf_model() or will be
    downloaded and loaded on first call by _get_hf_pipeline().

    Parameters
    ----------
    question         : str
        The user's question.
    retrieved_chunks : list[dict]
        Context chunks to ground the answer in.
    model_id         : str
        HuggingFace model identifier (e.g. 'google/flan-t5-base').
    max_tokens       : int
        Maximum new tokens to generate.

    Returns
    -------
    str
        Generated answer text, stripped of leading/trailing whitespace.
    """
    entry   = _get_hf_pipeline(model_id)
    context = _format_context(retrieved_chunks)

    if entry[0] == "seq2seq":
        # Flan-T5 / BART: run tokenizer → model.generate() → decode
        _, tokenizer, model = entry
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}\n"
            f"Answer:"
        )
        import torch
        inputs  = tokenizer(prompt, return_tensors="pt",
                            truncation=True, max_length=1024)
        with torch.no_grad():
            out_ids = model.generate(**inputs, max_new_tokens=max_tokens)
        answer = tokenizer.decode(out_ids[0], skip_special_tokens=True).strip()

    else:
        # Causal / instruction model: use chat messages if supported
        _, pipe = entry
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ]
        try:
            # Models with apply_chat_template (Zephyr, Mistral-Instruct, Llama-3 …)
            out = pipe(messages, max_new_tokens=max_tokens,
                       do_sample=True, temperature=0.1, return_full_text=False)
            answer = out[0]["generated_text"].strip()
        except Exception:
            # Fallback: plain string prompt
            prompt = (
                f"<|system|>{SYSTEM_PROMPT}</s>\n"
                f"<|user|>Context:\n{context}\n\nQuestion: {question}</s>\n"
                f"<|assistant|>"
            )
            out = pipe(prompt, max_new_tokens=max_tokens,
                       do_sample=True, temperature=0.1, return_full_text=False)
            answer = out[0]["generated_text"].strip()

    return answer


# ---------------------------------------------------------------------------
# CLI quick-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Minimal smoke test (requires ANTHROPIC_API_KEY)
    dummy_chunks = [
        {
            "chunk_id": "aap_p051_fixed_000",
            "text":     "Febrile seizures typically occur in children aged 6 months to 5 years. "
                        "They are associated with rapid temperature rises and are usually benign.",
            "score":    0.92,
            "metadata": {"source": "AAP_Case-Based.pdf", "page": 51},
        }
    ]
    answer = generate_answer(
        "At what age do febrile seizures typically occur?",
        dummy_chunks
    )
    print(answer)
