"""
app.py — Flask server for the Pediatric RAG pipeline demo.
Routes:
  /              Demo page
  /build         Rebuild index page
  /eval          Evaluation dashboard
  /ablation      Ablation study
  /goldset       Gold set editor
"""

import os
import sys
import json
import time
import queue
import threading
import subprocess
import statistics
from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

sys.path.insert(0, str(Path(__file__).parent / "src"))
from src.rag_system import answer as rag_answer
import generation as _generation   # same module object loaded by rag_system
from src.tutor_agent import (
    new_session  as tutor_new_session,
    chat_stream  as tutor_chat_stream,
    get_session_stats as tutor_stats,
    list_sessions as tutor_list_sessions,
    load_session  as tutor_load_session,
)

app = Flask(__name__)

PROJECT_ROOT  = Path(__file__).parent
BUILD_SCRIPT  = PROJECT_ROOT / "src" / "build_index.py"
GOLD_PATH     = PROJECT_ROOT / "eval" / "gold_set.jsonl"
LABELS_PATH   = PROJECT_ROOT / "eval" / "manual_labels.json"
ABLATION_PATH = PROJECT_ROOT / "eval" / "ablation_results.json"
INDEX_DIR     = PROJECT_ROOT / "index"

# ── Allowed models ─────────────────────────────────────────────────────────────
CLAUDE_MODELS = {"claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-opus-4-7"}
HF_MODELS     = {"google/flan-t5-base", "google/flan-t5-large",
                 "HuggingFaceH4/zephyr-7b-beta", "mistralai/Mistral-7B-Instruct-v0.2"}
ALLOWED_MODELS = CLAUDE_MODELS | HF_MODELS

# ── Shared state ───────────────────────────────────────────────────────────────
_build = {"running": False, "queue": queue.Queue(), "exit_code": None}
_eval  = {"running": False, "queue": queue.Queue()}

# ══════════════════════════════════════════════════════════════════════════════
# Pages
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():       return render_template("index.html")

@app.route("/build")
def build_page():  return render_template("build.html")

@app.route("/eval")
def eval_page():   return render_template("eval.html")

@app.route("/ablation")
def ablation_page(): return render_template("ablation.html")

@app.route("/goldset")
def goldset_page(): return render_template("goldset.html")

@app.route("/help")
def help_page(): return render_template("help.html")

@app.route("/qa")
def qa_page(): return render_template("qa.html")

@app.route("/tutor")
def tutor_page(): return render_template("tutor.html")

@app.route("/agent-explained")
def agent_explained(): return render_template("agent_explained.html")


# ══════════════════════════════════════════════════════════════════════════════
# Tutor Agent  /tutor/*
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/tutor/new", methods=["POST"])
def tutor_new():
    sid = tutor_new_session()
    return jsonify({"session_id": sid})


@app.route("/tutor/chat", methods=["POST"])
def tutor_chat():
    data       = request.get_json(force=True)
    session_id = (data.get("session_id") or "").strip()
    message    = (data.get("message")    or "").strip()
    if not message:
        return jsonify({"error": "No message"}), 400

    def _generate():
        for event in tutor_chat_stream(session_id, message):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        yield "data: __DONE__\n\n"

    return Response(
        stream_with_context(_generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/tutor/stats/<session_id>")
def tutor_session_stats(session_id):
    return jsonify(tutor_stats(session_id))


@app.route("/tutor/sessions")
def tutor_sessions_list():
    return jsonify(tutor_list_sessions())


@app.route("/tutor/load/<session_id>", methods=["POST"])
def tutor_load(session_id):
    found = tutor_load_session(session_id)
    if not found:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(tutor_stats(session_id))


@app.route("/tutor/log/<session_id>")
def tutor_log(session_id):
    from src.tutor_agent import _sessions
    tutor_load_session(session_id)
    s = _sessions.get(session_id, {})
    return jsonify(s.get("call_log", []))


@app.route("/tutor/history/<session_id>")
def tutor_history(session_id):
    from src.tutor_agent import _sessions
    tutor_load_session(session_id)
    s = _sessions.get(session_id, {})
    messages = []
    activity  = []   # tool call events for the feed

    for m in s.get("history", []):
        role    = m.get("role", "")
        content = m.get("content", "")

        if isinstance(content, str):
            if role in ("user", "assistant") and content.strip():
                messages.append({"role": role, "text": content.strip()})
            continue

        if not isinstance(content, list):
            continue

        text_parts = []
        for block in content:
            btype = block.get("type", "")
            if btype == "text" and block.get("text", "").strip():
                text_parts.append(block["text"].strip())
            elif btype == "tool_use":
                activity.append({
                    "event": "tool_call",
                    "tool":  block.get("name", ""),
                    "input": block.get("input", {}),
                })
            elif btype == "tool_result":
                raw = block.get("content", "")
                if isinstance(raw, list):
                    raw = " ".join(b.get("text","") for b in raw if b.get("type")=="text")
                try:
                    result = json.loads(raw) if isinstance(raw, str) else raw
                except Exception:
                    result = {"text": str(raw)[:200]}
                activity.append({
                    "event":  "tool_result",
                    "tool_id": block.get("tool_use_id", ""),
                    "result": result,
                })

        if text_parts and role in ("user", "assistant"):
            text = " ".join(text_parts)
            # skip [System:...] injections — not real chat messages
            if not text.startswith("[System:"):
                messages.append({"role": role, "text": text})

    # pair tool_calls with their results so the frontend can render one card each
    paired = []
    pending = {}   # tool_use_id -> activity entry
    tool_order = []
    for ev in activity:
        if ev["event"] == "tool_call":
            key = ev["tool"]
            pending[key] = ev
            tool_order.append(key)
        elif ev["event"] == "tool_result":
            # match by order since tool_use_id cross-ref may be complex
            if tool_order:
                key = tool_order.pop(0)
                call = pending.pop(key, {})
                paired.append({
                    "tool":   call.get("tool", key),
                    "input":  call.get("input", {}),
                    "result": ev["result"],
                })
    # flush any unmatched calls
    for key in tool_order:
        call = pending.get(key, {})
        paired.append({"tool": call.get("tool", key), "input": call.get("input", {}), "result": None})

    return jsonify({"messages": messages, "activity": paired})


# ══════════════════════════════════════════════════════════════════════════════
# Demo  /ask
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/ask", methods=["POST"])
def ask():
    data     = request.get_json(force=True)
    question = (data.get("question") or "").strip()
    strategy = data.get("strategy", "fixed")
    k        = int(data.get("k", 5))
    model    = data.get("model", "claude-haiku-4-5-20251001")

    if not question:               return jsonify({"error": "No question provided"}), 400
    if strategy not in ("fixed", "paragraph"): strategy = "fixed"
    if model not in ALLOWED_MODELS:            model = "claude-haiku-4-5-20251001"
    k = max(1, min(k, 10))

    try:
        t0 = time.time()
        result = rag_answer(question, strategy=strategy, k=k, model=model)
        result["latency"] = round(time.time() - t0, 2)
        result["model"]   = model
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── HuggingFace model download status ─────────────────────────────────────────

@app.route("/hf/status")
def hf_status():
    """Return download/load status for every HuggingFace model seen so far.

    Shape: { "google/flan-t5-base": {"state": "...", "progress": 0-100, "detail": "..."}, … }
    The frontend polls this to drive the progress bar.
    """
    return jsonify(_generation._hf_load_status)


@app.route("/hf/load", methods=["POST"])
def hf_load():
    """Start downloading and loading a HuggingFace model in a background thread.

    Body: { "model_id": "google/flan-t5-base" }
    Returns: { "status": "started" | "already_running" | "already_ready" }
    """
    model_id = (request.get_json(force=True) or {}).get("model_id", "")
    if model_id not in HF_MODELS:
        return jsonify({"error": f"Unknown model '{model_id}'"}), 400

    cur = _generation._hf_load_status.get(model_id, {})
    if isinstance(cur, dict) and cur.get("state") in ("downloading", "loading"):
        return jsonify({"status": "already_running"})
    if isinstance(cur, dict) and cur.get("state") == "ready":
        return jsonify({"status": "already_ready"})

    def _bg():
        _generation.prefetch_hf_model(model_id)

    threading.Thread(target=_bg, daemon=True).start()
    return jsonify({"status": "started"})


# ── Chunk text lookup ──────────────────────────────────────────────────────────
_chunk_cache: dict = {}

def _load_chunk_cache():
    if _chunk_cache:
        return
    for name in ("fixed", "paragraph"):
        p = INDEX_DIR / f"{name}_chunks.json"
        if p.exists():
            with open(p, encoding="utf-8") as f:
                for c in json.load(f):
                    _chunk_cache[c["chunk_id"]] = c

@app.route("/chunk/<chunk_id>")
def chunk_detail(chunk_id):
    _load_chunk_cache()
    c = _chunk_cache.get(chunk_id)
    if not c:
        return jsonify({"error": "Chunk not found"}), 404
    return jsonify(c)


# ══════════════════════════════════════════════════════════════════════════════
# Build  /build/*
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/build/run", methods=["POST"])
def build_run():
    if _build["running"]:
        return jsonify({"error": "A build is already running."}), 409

    data       = request.get_json(force=True)
    strategy   = data.get("strategy", "both")
    chunk_size = max(50,  min(int(data.get("chunk_size", 400)), 2000))
    overlap    = max(0,   min(int(data.get("overlap",    50)),  chunk_size - 1))
    if strategy not in ("fixed", "paragraph", "both"): strategy = "both"

    while not _build["queue"].empty():
        try: _build["queue"].get_nowait()
        except queue.Empty: break

    def _run():
        _build["running"] = True
        _build["exit_code"] = None
        cmd = [sys.executable, str(BUILD_SCRIPT),
               "--strategy", strategy, "--chunk-size", str(chunk_size), "--overlap", str(overlap)]
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8", errors="replace",
                                    bufsize=1, cwd=str(PROJECT_ROOT), env=env)
            for line in proc.stdout:
                _build["queue"].put(line.rstrip())
            proc.wait()
            _build["exit_code"] = proc.returncode
        except Exception as e:
            _build["queue"].put(f"ERROR: {e}")
            _build["exit_code"] = 1
        finally:
            _build["queue"].put(f"__DONE__{_build['exit_code']}")
            _build["running"] = False
            _chunk_cache.clear()   # invalidate cache after rebuild

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"started": True})


@app.route("/build/stream")
def build_stream():
    def _gen():
        while True:
            try:
                line = _build["queue"].get(timeout=30)
                yield f"data: {line}\n\n"
                if line.startswith("__DONE__"): break
            except queue.Empty:
                yield "data: __PING__\n\n"
    return Response(stream_with_context(_gen()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/build/status")
def build_status():
    return jsonify({"running": _build["running"], "exit_code": _build["exit_code"]})


# ══════════════════════════════════════════════════════════════════════════════
# Evaluation  /eval/*
# ══════════════════════════════════════════════════════════════════════════════

def _load_gold():
    if not GOLD_PATH.exists(): return []
    records = []
    with open(GOLD_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _extract_sources(chunk_ids):
    return {cid.split("_")[0] for cid in chunk_ids}

def _extract_pages(chunk_ids):
    pages = set()
    for cid in chunk_ids:
        for part in cid.split("_"):
            if part.startswith("p") and part[1:].isdigit():
                pages.add(int(part[1:]))
    return pages

def _hit(retrieved, gold_ids):
    if not gold_ids: return True
    r_ids = {c["chunk_id"] for c in retrieved}
    if r_ids & set(gold_ids): return True
    gold_src   = _extract_sources(gold_ids)
    gold_pages = _extract_pages(gold_ids)
    for c in retrieved:
        src  = c["metadata"].get("doc_id_prefix", c["chunk_id"].split("_")[0])
        page = int(c["metadata"].get("page", 0))
        if src in gold_src and any(abs(page - gp) <= 2 for gp in gold_pages):
            return True
    return False

def _precision(retrieved, gold_ids):
    if not retrieved or not gold_ids: return 0.0
    gold_src = _extract_sources(gold_ids)
    correct  = sum(1 for c in retrieved
                   if c["metadata"].get("doc_id_prefix",
                      c["chunk_id"].split("_")[0]) in gold_src)
    return correct / len(retrieved)


@app.route("/eval/run", methods=["POST"])
def eval_run():
    if _eval["running"]:
        return jsonify({"error": "Evaluation already running"}), 409

    data     = request.get_json(force=True)
    strategy = data.get("strategy", "fixed")
    k        = max(1, min(int(data.get("k", 5)), 10))
    limit    = data.get("limit", None)
    model    = data.get("model", "claude-haiku-4-5-20251001")
    if strategy not in ("fixed", "paragraph"): strategy = "fixed"
    if model not in ALLOWED_MODELS:            model = "claude-haiku-4-5-20251001"

    while not _eval["queue"].empty():
        try: _eval["queue"].get_nowait()
        except queue.Empty: break

    def _run():
        _eval["running"] = True
        gold = _load_gold()
        if limit: gold = gold[:int(limit)]

        hits, precs, lats = [], [], []
        cat_hits: dict[str, list] = {}

        _eval["queue"].put(json.dumps({"type": "start", "n": len(gold),
                                       "strategy": strategy, "k": k}))
        for i, item in enumerate(gold):
            q       = item["question"]
            gold_ids= item.get("must_cite_chunk_ids", [])
            cat     = item.get("category", "unknown")
            try:
                t0  = time.time()
                res = rag_answer(q, strategy=strategy, k=k, model=model)
                lat = round(time.time() - t0, 2)
                h   = _hit(res["retrieved_chunks"], gold_ids)
                pr  = _precision(res["retrieved_chunks"], gold_ids)
                hits.append(h); precs.append(pr); lats.append(lat)
                cat_hits.setdefault(cat, []).append(h)
                _eval["queue"].put(json.dumps({
                    "type":      "result",
                    "idx":       i,
                    "question":  q,
                    "category":  cat,
                    "hit":       h,
                    "precision": round(pr, 3),
                    "latency":   lat,
                    "answer":    res["answer"],
                    "sources":   res["sources"],
                    "ref_answer":item.get("reference_answer", ""),
                    "gold_ids":  gold_ids,
                }))
            except Exception as e:
                _eval["queue"].put(json.dumps({
                    "type": "result", "idx": i, "question": q,
                    "category": cat, "hit": False, "precision": 0,
                    "latency": 0, "answer": f"ERROR: {e}",
                    "sources": [], "ref_answer": "", "gold_ids": gold_ids,
                }))

        n = len(hits)
        cat_summary = {cat: {"hit": round(sum(v)/len(v), 3), "n": len(v)}
                       for cat, v in cat_hits.items()}
        _eval["queue"].put(json.dumps({
            "type":       "summary",
            "n":          n,
            "hit_at_k":   round(sum(hits)/n, 3) if n else 0,
            "precision":  round(sum(precs)/n, 3) if n else 0,
            "latency":    round(statistics.mean(lats), 2) if lats else 0,
            "categories": cat_summary,
            "strategy":   strategy,
            "k":          k,
        }))
        _eval["queue"].put("__DONE__")
        _eval["running"] = False

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"started": True})


@app.route("/eval/stream")
def eval_stream():
    def _gen():
        while True:
            try:
                msg = _eval["queue"].get(timeout=60)
                yield f"data: {msg}\n\n"
                if msg == "__DONE__": break
            except queue.Empty:
                yield "data: __PING__\n\n"
    return Response(stream_with_context(_gen()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/eval/label", methods=["POST"])
def eval_label():
    data = request.get_json(force=True)
    labels = {}
    if LABELS_PATH.exists():
        with open(LABELS_PATH, encoding="utf-8") as f:
            labels = json.load(f)
    labels[str(data["idx"])] = {
        "label":    data["label"],
        "question": data.get("question", ""),
        "note":     data.get("note", ""),
    }
    with open(LABELS_PATH, "w", encoding="utf-8") as f:
        json.dump(labels, f, ensure_ascii=False, indent=2)
    return jsonify({"saved": True})


@app.route("/eval/labels")
def eval_labels():
    if not LABELS_PATH.exists(): return jsonify({})
    with open(LABELS_PATH, encoding="utf-8") as f:
        return jsonify(json.load(f))


@app.route("/eval/status")
def eval_status():
    return jsonify({"running": _eval["running"]})


# ══════════════════════════════════════════════════════════════════════════════
# Ablation  /ablation/*
# ══════════════════════════════════════════════════════════════════════════════

def _load_ablation():
    if not ABLATION_PATH.exists(): return []
    with open(ABLATION_PATH, encoding="utf-8") as f:
        return json.load(f)

def _save_ablation(rows):
    with open(ABLATION_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


@app.route("/ablation/results")
def ablation_results():
    return jsonify(_load_ablation())


@app.route("/ablation/run", methods=["POST"])
def ablation_run():
    data     = request.get_json(force=True)
    strategy = data.get("strategy", "fixed")
    k        = max(1, min(int(data.get("k", 5)), 10))
    limit    = max(5, min(int(data.get("limit", 20)), 52))
    label    = data.get("label", f"{strategy} k={k}").strip()
    notes    = data.get("notes", "").strip()
    model    = data.get("model", "claude-haiku-4-5-20251001")
    if strategy not in ("fixed", "paragraph"): strategy = "fixed"
    if model not in ALLOWED_MODELS:            model = "claude-haiku-4-5-20251001"

    gold = _load_gold()[:limit]
    if not gold: return jsonify({"error": "Gold set not found"}), 404

    hits, precs, lats = [], [], []
    cat_hits: dict[str, list] = {}
    t_start = time.time()

    for item in gold:
        gold_ids = item.get("must_cite_chunk_ids", [])
        cat      = item.get("category", "unknown")
        try:
            t0  = time.time()
            res = rag_answer(item["question"], strategy=strategy, k=k, model=model)
            lat = time.time() - t0
            h   = _hit(res["retrieved_chunks"], gold_ids)
            pr  = _precision(res["retrieved_chunks"], gold_ids)
        except Exception:
            h, pr, lat = False, 0.0, 0.0
        hits.append(h); precs.append(pr); lats.append(lat)
        cat_hits.setdefault(cat, []).append(h)

    n = len(hits)
    row = {
        "label":      label,
        "strategy":   strategy,
        "k":          k,
        "limit":      limit,
        "hit_at_k":   round(sum(hits)/n, 3) if n else 0,
        "precision":  round(sum(precs)/n, 3) if n else 0,
        "latency":    round(statistics.mean(lats), 2) if lats else 0,
        "total_time": round(time.time() - t_start, 1),
        "notes":      notes,
        "categories": {cat: round(sum(v)/len(v), 3) for cat, v in cat_hits.items()},
        "timestamp":  time.strftime("%Y-%m-%d %H:%M"),
    }
    rows = _load_ablation()
    rows.append(row)
    _save_ablation(rows)
    return jsonify(row)


@app.route("/ablation/delete", methods=["POST"])
def ablation_delete():
    idx = int(request.get_json(force=True).get("idx", -1))
    rows = _load_ablation()
    if 0 <= idx < len(rows):
        rows.pop(idx)
        _save_ablation(rows)
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════════════════════════════════
# Gold Set  /goldset/*
# ══════════════════════════════════════════════════════════════════════════════

def _load_gold_list():
    return _load_gold()

def _save_gold_list(records):
    with open(GOLD_PATH, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


@app.route("/goldset/questions")
def goldset_questions():
    return jsonify(_load_gold_list())


@app.route("/goldset/save", methods=["POST"])
def goldset_save():
    data = request.get_json(force=True)
    records = _load_gold_list()
    idx = data.get("idx", -1)
    record = {
        "question":           (data.get("question") or "").strip(),
        "reference_answer":   (data.get("reference_answer") or "").strip(),
        "must_cite_chunk_ids": [x.strip() for x in
                                (data.get("must_cite_chunk_ids") or "").split(",") if x.strip()],
        "category":           data.get("category", "factual"),
    }
    if not record["question"]:
        return jsonify({"error": "Question required"}), 400
    if idx >= 0 and idx < len(records):
        records[idx] = record
    else:
        records.append(record)
    _save_gold_list(records)
    return jsonify({"saved": True, "total": len(records)})


@app.route("/goldset/delete", methods=["POST"])
def goldset_delete():
    idx = int(request.get_json(force=True).get("idx", -1))
    records = _load_gold_list()
    if 0 <= idx < len(records):
        records.pop(idx)
        _save_gold_list(records)
        return jsonify({"ok": True, "total": len(records)})
    return jsonify({"error": "Index out of range"}), 400


# ══════════════════════════════════════════════════════════════════════════════
# OSCE AI Analysis  /osce-ai/*
# ══════════════════════════════════════════════════════════════════════════════

OSCE_AGENT_STEPS = [
    ("data_read",      "🔍 קורא נתוני המבחן",              "מזהה מספר נבחנים, תחנות, בוחנים ומבנה הנתונים"),
    ("reliability",    "📊 מנתח מהימנות",                  "בוחן Cronbach Alpha, ICC ו-Weighted Kappa"),
    ("stations",       "🏥 בוחן תחנות",                    "מזהה תחנות חלשות לפי SQI, Pass Rate ו-BRM"),
    ("examiners",      "👁️ בוחן כיול בוחנים",             "מאתר בוחנים מחמירים או מקלים ביחס לממוצע"),
    ("recommendations","💡 מגבש המלצות",                   "מסכם ממצאים ומנסח פעולות נדרשות למרכז הקורס"),
]

OLLAMA_MODEL   = "llama3.1:8b"
OLLAMA_BASE    = "http://localhost:11434"

# AI engine settings (runtime-configurable via /osce-ai/config)
_ai_config = {
    "engine": "ollama",      # "ollama" | "runai" | "openai"
    "runai_url": "",
    "runai_model": "",
    "openai_key": "",
    "openai_model": "gpt-4o-mini",
}

def _osce_ollama_call(prompt: str, system: str) -> str:
    import urllib.request, urllib.error
    payload = json.dumps({
        "model":  OLLAMA_MODEL,
        "prompt": f"{system}\n\n{prompt}",
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 900},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_BASE}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=240) as r:
            data = json.loads(r.read().decode("utf-8"))
            return data.get("response", "").strip()
    except urllib.error.URLError as e:
        return f"שגיאת חיבור ל-Ollama: {e.reason}. ודא ש-Ollama רץ (ollama serve)."
    except Exception as e:
        return f"שגיאה: {e}"

def _osce_runai_call(prompt: str, system: str) -> str:
    """Call RunAI / vLLM OpenAI-compatible endpoint — no token required."""
    import urllib.request, urllib.error
    url   = _ai_config["runai_url"].rstrip("/")
    model = _ai_config["runai_model"]
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system",  "content": system},
            {"role": "user",    "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 900,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{url}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=240) as r:
            data = json.loads(r.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except urllib.error.URLError as e:
        return f"שגיאת חיבור ל-RunAI: {e.reason}"
    except Exception as e:
        return f"שגיאה: {e}"

def _osce_openai_call(prompt: str, system: str) -> str:
    """Call OpenAI API (or any OpenAI-compatible endpoint with a key)."""
    import urllib.request, urllib.error
    key   = _ai_config.get("openai_key", "")
    model = _ai_config.get("openai_model", "gpt-4o-mini")
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 900,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload, headers=headers, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except urllib.error.URLError as e:
        return f"שגיאת חיבור ל-OpenAI: {e.reason}"
    except Exception as e:
        return f"שגיאה: {e}"

def _osce_claude_call(prompt: str, system: str) -> str:
    eng = _ai_config["engine"]
    if eng == "runai" and _ai_config["runai_url"] and _ai_config["runai_model"]:
        return _osce_runai_call(prompt, system)
    if eng == "openai":
        return _osce_openai_call(prompt, system)
    return _osce_ollama_call(prompt, system)


@app.route("/osce-ai/analyze", methods=["POST"])
def osce_ai_analyze():
    data = request.get_json(force=True) or {}

    def _stream():
        system_he = """אתה מנהל מרכז בחינות OSCE בכיר עם 20 שנות ניסיון בהערכה קלינית ופסיכומטריה רפואית.
תפקידך: לנתח תוצאות בחינה ולהסביר את המשמעות הקלינית והפסיכומטרית שלהן.

כללי כתיבה:
- כתוב בעברית ברורה, מקצועית ונגישה למרכז הקורס
- פרט כל ממצא והסבר מה המשמעות שלו ביחס לאיכות הבחינה ולנבחנים
- השתמש ברמזי צבע: 🟢 טוב, 🟡 דורש מעקב, 🟠 דורש פעולה, 🔴 דחוף לטיפול
- בכל נקודה ציין: מה הנתון → מה המשמעות → מה צריך לעשות
- ענה בפורמט: שורות מופרדות, כל ממצא בשורה חדשה שמתחילה ברמז הצבע המתאים
- הסבר מושגים מקצועיים (Alpha, ICC, SQI) בשפה פשוטה בסוגריים
- אל תמציא נתונים שלא סופקו לך"""

        metrics   = data.get("metrics",   {})
        stations  = data.get("stations",  [])
        examiners = data.get("examiners", [])
        custom_p  = data.get("prompts",   {})   # custom prompts from the browser editor

        metrics_txt   = "\n".join(f"  {k}: {v}" for k, v in metrics.items())
        stations_txt  = "\n".join(
            f"  {s.get('name','?')}: ממוצע={s.get('avg','?')}, SQI={s.get('sqi','?')}, PassRate={s.get('passRate','?')}%, Cut BRM={s.get('cut','?')}"
            for s in stations[:12]
        )
        examiners_txt = "\n".join(
            f"  {e.get('name','?')}: ממוצע={e.get('avg','?')}, פער מהממוצע={e.get('gap','?')}, סטטוס={e.get('status','?')}"
            for e in examiners[:10]
        )

        # Use custom system prompt if provided, else fall back to default
        if custom_p.get("system", "").strip():
            system_he = custom_p["system"].strip()

        def _step_prompt(step_id, data_block, default_instruction):
            """Prepend exam data to either the custom or default instruction."""
            instruction = custom_p.get(step_id, "").strip() or default_instruction
            return f"{data_block}\n\n{instruction}"

        prompts = {
            "data_read": _step_prompt(
                "data_read",
                f"נתוני הבחינה:\n{metrics_txt}",
                "תאר בשורות ברורות מה רואים בנתונים הכלליים: גודל הקבוצה, מבנה הבחינה, ממוצע הציונים ומה בולט לעין ראשונה. "
                "לכל נתון — הסבר מה המשמעות שלו לגבי תקינות הבחינה. "
                "השתמש בסמלי הצבע 🟢🟡🟠🔴 לפי חומרת הממצא."
            ),
            "reliability": _step_prompt(
                "reliability",
                f"מדדי מהימנות של הבחינה:\n{metrics_txt}",
                "נתח כל מדד בנפרד: מה הערך שהתקבל, מה הסף המקובל לבחינת high-stakes, ומה המשמעות לגבי אמינות הבחינה. "
                "Cronbach Alpha: מעל 0.80 נהדר, 0.70-0.79 מקובל, מתחת ל-0.70 בעייתי. "
                "ICC: מעל 0.75 טוב, 0.50-0.75 מתון, מתחת ל-0.50 חלש. "
                "Weighted Kappa: מעל 0.60 טוב, 0.40-0.60 מתון, מתחת ל-0.40 חלש. "
                "לאחר כל מדד: האם תוצאות הבחינה הזאת ניתנות להגנה בפני ועדת אקרדיטציה? הסבר."
            ),
            "stations": _step_prompt(
                "stations",
                f"נתוני תחנות:\n{stations_txt}\n\nמדדים כלליים:\n{metrics_txt}",
                "עבור על תחנות הבחינה וזהה: תחנות חזקות, תחנות הדורשות מעקב, ותחנות דחופות לבדיקה. "
                "לכל תחנה בעייתית הסבר מה הבעיה הספציפית ומה ההשלכה על הנבחנים. "
                "אם אין נתוני תחנות ספציפיים — ציין זאת ונתח מה שיש."
            ),
            "examiners": _step_prompt(
                "examiners",
                f"נתוני בוחנים:\n{examiners_txt}\n\nממוצע הבחינה:\n{metrics_txt}",
                "בחן את דפוס הציונים של כל בוחן. בוחן מחמיר (גבוה מהממוצע ב-10%+) ובוחן מקל (נמוך מהממוצע ב-10%+) "
                "יוצרים חוסר הוגנות בין נבחנים. הסבר מה ההשפעה הקונקרטית ומה כיול בוחנים צריך לכלול."
            ),
            "recommendations": _step_prompt(
                "recommendations",
                f"סיכום נתוני הבחינה:\nמדדים:\n{metrics_txt}\nתחנות:\n{stations_txt}\nבוחנים:\n{examiners_txt}",
                "כמנהל מרכז בחינות, כתוב 5 המלצות ממוספרות וברורות למרכז הקורס. "
                "לכל המלצה: 🔴/🟠/🟡/🟢 לפי דחיפות, כותרת קצרה, הסבר מה לעשות בדיוק ולמה זה חשוב. "
                "בסוף הוסף שורת סיכום: האם הבחינה עומדת בסטנדרט?"
            ),
        }

        for step_id, title, subtitle in OSCE_AGENT_STEPS:
            yield f"data: {json.dumps({'type':'step_start','step_id':step_id,'title':title,'subtitle':subtitle}, ensure_ascii=False)}\n\n"

            result = _osce_claude_call(prompts[step_id], system_he)

            yield f"data: {json.dumps({'type':'step_done','step_id':step_id,'title':title,'content':result}, ensure_ascii=False)}\n\n"

        yield "data: __DONE__\n\n"

    return Response(
        stream_with_context(_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.route("/osce")
def osce_page():
    from flask import send_file
    return send_file(r"C:\Users\ygross\Downloads\OSCE_Analytics_Pro_v16_Button_Progress_ItemAnalysis_FIXED.html", mimetype="text/html")

@app.route("/osce-form")
def osce_form_page():
    from flask import send_file
    return send_file(PROJECT_ROOT / "static" / "osce_form_v2.html", mimetype="text/html")

@app.route("/portal")
def osce_portal():
    from flask import send_file
    return send_file(PROJECT_ROOT / "static" / "portal.html", mimetype="text/html")


@app.route("/osce-prep/analyze", methods=["POST"])
def osce_prep_analyze():
    data = request.get_json(force=True) or {}

    def _stream():
        custom_p = data.get("prompts", {})
        reports  = data.get("reports", {})
        exam_name = data.get("examName", "לא צוין")
        exam_date = data.get("examDate", "לא צוין")
        manager   = data.get("manager",  "לא צוין")

        system_he = custom_p.get("system", "").strip() or (
            "אתה מהנדס מרכז סימולציה מנוסה ומנהל בחינות OSCE בכיר. "
            "תפקידך: לבחון את המסמכים שהוכנו לקראת הבחינה ולזהות בעיות וסיכונים. "
            "כתוב בעברית. השתמש ב: 🟢 תקין, 🟡 דורש תשומת לב, 🟠 בעיה, 🔴 עצור-חובה לטפל. "
            "לכל ממצא: מה הבעיה → מה הסיכון → מה לעשות. אל תמציא נתונים."
        )

        header = (
            f"פרטי הבחינה: {exam_name} | תאריך: {exam_date} | מרכז קורס: {manager}\n\n"
        )

        def _rpt(key):
            r = (reports.get(key) or "").strip()
            return r if r else "לא בוצעה בדיקה / לא הועלה קובץ."

        step_defs = [
            ("schedule",      "📅 בוחן סדר יום",             "schedule",
             custom_p.get("schedule","").strip() or
             "בחן את דוח הבדיקה של סדר היום. זהה חפיפות זמן, תחנות חסרות, חדרים ללא מדריך, "
             "בעיות לוגיסטיות. לכל בעיה — ציין את הסיכון לבחינה."),
            ("questionnaire", "📝 בוחן שאלונים",             "questionnaire",
             custom_p.get("questionnaire","").strip() or
             "בחן את דוח בדיקת השאלונים. זהה שאלות חסרות, כפולות, חוסר בהערכה כללית, "
             "בעיות במבנה. לכל בעיה — ציין את ההשפעה על הנבחנים."),
            ("participants",  "👥 בוחן שיבוץ משתתפים וצוות", "participants",
             custom_p.get("participants","").strip() or
             "בחן את דוחות שיבוץ המשתתפים והצוות. זהה שורות ריקות, כפילויות, "
             "חדרים ללא אחראי, נתונים חסרים. לכל בעיה — ציין את הסיכון האופרטיבי."),
            ("scenarios",     "🎭 בוחן שדות תרחישים",        "scenarios",
             custom_p.get("scenarios","").strip() or
             "בחן את דוח שדות התרחישים. זהה שדות ריקים, חוסר בסיפור מקרה, "
             "תרחישים ללא הנחיות מדריך, טקסטים חשודים."),
            ("final",         "💡 המלצות לפני הבחינה",       None,
             custom_p.get("final","").strip() or
             "לאחר בחינת כל הדוחות — כתוב 5 המלצות דחופות ממוספרות לפני הבחינה. "
             "כל המלצה: 🔴/🟠/🟡/🟢 לפי דחיפות + מה לעשות בדיוק. "
             "בסוף שורה: האם הבחינה מוכנה לביצוע?"),
        ]

        all_reports_txt = ""
        for _, _, rkey, _ in step_defs[:-1]:
            if rkey:
                all_reports_txt += f"\n--- {rkey} ---\n{_rpt(rkey)}\n"

        for step_id, title, rkey, instruction in step_defs:
            yield f"data: {json.dumps({'type':'step_start','step_id':step_id,'title':title}, ensure_ascii=False)}\n\n"

            if rkey:
                prompt = f"{header}דוח בדיקה — {title}:\n{_rpt(rkey)}\n\n{instruction}"
            else:
                prompt = f"{header}סיכום כל הדוחות:\n{all_reports_txt}\n\n{instruction}"

            result = _osce_ollama_call(prompt, system_he)
            yield f"data: {json.dumps({'type':'step_done','step_id':step_id,'title':title,'content':result}, ensure_ascii=False)}\n\n"

        yield "data: __DONE__\n\n"

    return Response(
        stream_with_context(_stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no","Access-Control-Allow-Origin":"*"},
    )


@app.route("/osce-prep/analyze", methods=["OPTIONS"])
def osce_prep_options():
    return Response("", headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
    })


@app.route("/osce-ai/config", methods=["GET"])
def osce_ai_config_get():
    return Response(
        json.dumps(_ai_config, ensure_ascii=False),
        mimetype="application/json",
        headers={"Access-Control-Allow-Origin": "*"},
    )

@app.route("/osce-ai/config", methods=["POST"])
def osce_ai_config_set():
    body = request.get_json(force=True) or {}
    for k in ("engine", "runai_url", "runai_model", "openai_key", "openai_model"):
        if k in body:
            _ai_config[k] = body[k].strip() if isinstance(body[k], str) else body[k]
    return Response(
        json.dumps({"ok": True, "config": _ai_config}, ensure_ascii=False),
        mimetype="application/json",
        headers={"Access-Control-Allow-Origin": "*"},
    )

@app.route("/osce-ai/config", methods=["OPTIONS"])
def osce_ai_config_options():
    return Response("", headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    })

@app.route("/osce-ai/ping")
def osce_ai_ping():
    import urllib.request, urllib.error

    if _ai_config["engine"] == "openai":
        ok = bool(_ai_config.get("openai_key"))
        model = _ai_config.get("openai_model", "gpt-4o-mini")
        return Response(
            json.dumps({"ok": ok, "model": model, "engine": "OpenAI",
                        "base": "api.openai.com", "engine_id": "openai"}, ensure_ascii=False),
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    if _ai_config["engine"] == "runai" and _ai_config["runai_url"] and _ai_config["runai_model"]:
        url = _ai_config["runai_url"].rstrip("/")
        ok = False
        try:
            with urllib.request.urlopen(f"{url}/v1/models", timeout=5) as r:
                ok = r.status == 200
        except Exception:
            ok = False
        return Response(
            json.dumps({"ok": ok, "model": _ai_config["runai_model"],
                        "engine": "RunAI (BGU)", "base": url, "engine_id": "runai"}, ensure_ascii=False),
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    # Default: probe Ollama
    model_name = OLLAMA_MODEL
    ok = False
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=3) as r:
            tags = json.loads(r.read().decode("utf-8"))
            models = [m["name"] for m in tags.get("models", [])]
            ok = any(m.startswith(OLLAMA_MODEL.split(":")[0]) for m in models)
            if models:
                matching = [m for m in models if m.startswith(OLLAMA_MODEL.split(":")[0])]
                model_name = matching[0] if matching else models[0]
    except Exception:
        ok = False
    return Response(
        json.dumps({"ok": ok, "model": model_name, "engine": "Ollama (local)",
                    "base": OLLAMA_BASE, "engine_id": "ollama"}, ensure_ascii=False),
        mimetype="application/json",
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.route("/osce-ai/analyze", methods=["OPTIONS"])
def osce_ai_options():
    return Response("", headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
    })


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting RAG demo at http://localhost:{port}")
    app.run(debug=True, port=port, threaded=True, use_reloader=True)
