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
# Main
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting RAG demo at http://localhost:{port}")
    app.run(debug=True, port=port, threaded=True, use_reloader=True)
