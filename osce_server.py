"""OSCE standalone server — port 5001"""
import json, os
from pathlib import Path
from flask import Flask, Response, request, send_file

PROJECT_ROOT = Path(__file__).parent
OLLAMA_MODEL = "llama3.1:8b"
OLLAMA_BASE  = "http://localhost:11434"
CONFIG_FILE  = PROJECT_ROOT / "osce_config.json"

_AI_DEFAULTS = {
    "engine": "ollama", "runai_url": "", "runai_model": "",
    "openai_key": "", "openai_model": "gpt-4o-mini",
}

def _load_config():
    if CONFIG_FILE.exists():
        try:
            return {**_AI_DEFAULTS, **json.loads(CONFIG_FILE.read_text(encoding="utf-8"))}
        except Exception:
            pass
    return dict(_AI_DEFAULTS)

def _save_config():
    CONFIG_FILE.write_text(json.dumps(_ai_config, ensure_ascii=False, indent=2), encoding="utf-8")

_ai_config = _load_config()
app = Flask(__name__)

# ── AI calls ──────────────────────────────────────────────────────────────────

def _ollama_call(prompt, system):
    import urllib.request, urllib.error
    payload = json.dumps({"model": OLLAMA_MODEL, "prompt": f"{system}\n\n{prompt}",
        "stream": False, "options": {"temperature": 0.3, "num_predict": 900}}).encode()
    req = urllib.request.Request(f"{OLLAMA_BASE}/api/generate",
        data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=240) as r:
            return json.loads(r.read())["response"].strip()
    except Exception as e:
        return f"שגיאה: {e}"

def _runai_call(prompt, system):
    import urllib.request, urllib.error
    url = _ai_config["runai_url"].rstrip("/")
    payload = json.dumps({"model": _ai_config["runai_model"], "messages": [
        {"role": "system", "content": system}, {"role": "user", "content": prompt},
    ], "temperature": 0.3, "max_tokens": 900}).encode()
    req = urllib.request.Request(f"{url}/v1/chat/completions",
        data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=240) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"שגיאה: {e}"

def _openai_call(prompt, system):
    import urllib.request
    key = _ai_config.get("openai_key", "")
    payload = json.dumps({"model": _ai_config.get("openai_model","gpt-4o-mini"), "messages": [
        {"role": "system", "content": system}, {"role": "user", "content": prompt},
    ], "temperature": 0.3, "max_tokens": 900}).encode()
    headers = {"Content-Type": "application/json"}
    if key: headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request("https://api.openai.com/v1/chat/completions",
        data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"שגיאה: {e}"

def ai_call(prompt, system, model_override=None):
    eng = _ai_config["engine"]
    if model_override:
        if eng == "runai":   _ai_config["runai_model"]  = model_override
        elif eng == "openai": _ai_config["openai_model"] = model_override
        else:
            global OLLAMA_MODEL; OLLAMA_MODEL = model_override
    if eng == "runai" and _ai_config["runai_url"] and _ai_config["runai_model"]:
        return _runai_call(prompt, system)
    if eng == "openai":
        return _openai_call(prompt, system)
    return _ollama_call(prompt, system)

# ── CORS helper ───────────────────────────────────────────────────────────────

def _cors(resp):
    resp.headers["Access-Control-Allow-Origin"]  = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp

# ── Static pages ──────────────────────────────────────────────────────────────

@app.route("/")
@app.route("/portal")
def portal(): return send_file(PROJECT_ROOT/"static"/"portal.html", mimetype="text/html")

@app.route("/osce")
def osce_page(): return send_file(
    r"C:\Users\ygross\Downloads\OSCE_Analytics_Pro_v16_Button_Progress_ItemAnalysis_FIXED.html",
    mimetype="text/html")

@app.route("/osce-form")
def osce_form(): return send_file(PROJECT_ROOT/"static"/"osce_form_v2.html", mimetype="text/html")

# ── Config ────────────────────────────────────────────────────────────────────

@app.route("/osce-ai/config", methods=["GET"])
def cfg_get(): return _cors(Response(json.dumps(_ai_config, ensure_ascii=False), mimetype="application/json"))

@app.route("/osce-ai/config", methods=["POST"])
def cfg_set():
    body = request.get_json(force=True) or {}
    for k in ("engine","runai_url","runai_model","openai_key","openai_model"):
        if k in body: _ai_config[k] = body[k].strip() if isinstance(body[k],str) else body[k]
    _save_config()
    return _cors(Response(json.dumps({"ok":True}, ensure_ascii=False), mimetype="application/json"))

@app.route("/osce-ai/config", methods=["OPTIONS"])
def cfg_opt(): return _cors(Response(""))

# ── Models ────────────────────────────────────────────────────────────────────

@app.route("/osce-ai/models")
def get_models():
    import urllib.request
    eng, models = _ai_config["engine"], []
    try:
        if eng == "ollama":
            with urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=4) as r:
                models = [m["name"] for m in json.loads(r.read()).get("models",[])]
        elif eng == "runai" and _ai_config["runai_url"]:
            with urllib.request.urlopen(_ai_config["runai_url"].rstrip("/")+"/v1/models", timeout=5) as r:
                models = [m["id"] for m in json.loads(r.read()).get("data",[])]
        elif eng == "openai":
            models = ["gpt-4o","gpt-4o-mini","gpt-4-turbo","gpt-3.5-turbo"]
    except Exception: pass
    current = _ai_config["runai_model"] if eng=="runai" else _ai_config["openai_model"] if eng=="openai" else OLLAMA_MODEL
    return _cors(Response(json.dumps({"models":models,"current":current,"engine":eng},ensure_ascii=False), mimetype="application/json"))

@app.route("/osce-ai/models", methods=["OPTIONS"])
def models_opt(): return _cors(Response(""))

# ── Ping ──────────────────────────────────────────────────────────────────────

@app.route("/osce-ai/ping")
def ping():
    import urllib.request
    eng = _ai_config["engine"]
    if eng == "openai":
        ok = bool(_ai_config.get("openai_key"))
        return _cors(Response(json.dumps({"ok":ok,"model":_ai_config["openai_model"],"engine":"OpenAI","base":"api.openai.com","engine_id":"openai"},ensure_ascii=False), mimetype="application/json"))
    if eng == "runai" and _ai_config["runai_url"]:
        url, ok = _ai_config["runai_url"].rstrip("/"), False
        try:
            with urllib.request.urlopen(f"{url}/v1/models", timeout=5) as r: ok = r.status==200
        except Exception: pass
        return _cors(Response(json.dumps({"ok":ok,"model":_ai_config["runai_model"],"engine":"RunAI (BGU)","base":url,"engine_id":"runai"},ensure_ascii=False), mimetype="application/json"))
    model_name, ok = OLLAMA_MODEL, False
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=3) as r:
            tags = json.loads(r.read()); models = [m["name"] for m in tags.get("models",[])]
            ok = any(m.startswith(OLLAMA_MODEL.split(":")[0]) for m in models)
            matching = [m for m in models if m.startswith(OLLAMA_MODEL.split(":")[0])]
            model_name = matching[0] if matching else (models[0] if models else OLLAMA_MODEL)
    except Exception: pass
    return _cors(Response(json.dumps({"ok":ok,"model":model_name,"engine":"Ollama (local)","base":OLLAMA_BASE,"engine_id":"ollama"},ensure_ascii=False), mimetype="application/json"))

# ── OSCE Analytics AI ─────────────────────────────────────────────────────────

OSCE_STEPS = [
    ("data_read",       "🔍 קורא נתוני המבחן",    "מזהה מספר נבחנים, תחנות, בוחנים ומבנה הנתונים"),
    ("reliability",     "📊 מנתח מהימנות",         "בוחן Cronbach Alpha, ICC ו-Weighted Kappa"),
    ("stations",        "🏥 בוחן תחנות",           "מזהה תחנות חלשות לפי SQI, Pass Rate ו-BRM"),
    ("examiners",       "👁️ בוחן כיול בוחנים",    "מאתר בוחנים מחמירים או מקלים ביחס לממוצע"),
    ("recommendations", "💡 מגבש המלצות",          "מסכם ממצאים ומנסח פעולות נדרשות למרכז הקורס"),
]

SYSTEM_HE = """אתה מנהל מרכז בחינות OSCE מנוסה. קיבלת נתוני בחינה מחושבים — נתח אותם ישירות.
כתוב תשובה ענייתית בעברית. השתמש בסמנים: 🟢 טוב · 🟡 מעקב · 🟠 פעולה · 🔴 דחוף.
אל תבקש נתונים נוספים — הנתונים המלאים כבר כלולים בפרומפט."""

@app.route("/osce-ai/analyze", methods=["POST"])
def osce_analyze():
    data      = request.get_json(force=True) or {}
    metrics   = data.get("metrics",   {})
    stations  = data.get("stations",  [])
    examiners = data.get("examiners", [])
    custom_p  = data.get("prompts",   {})
    model_sel = data.get("model",     None)
    system    = custom_p.get("system","").strip() or SYSTEM_HE

    # Raw computed data
    metrics_txt   = "\n".join(f"  {k}: {v}" for k,v in metrics.items())
    stations_txt  = "\n".join(
        f"  {s.get('name','?')}: ממוצע={s.get('avg','?')}, SD={s.get('sd','?')}, SQI={s.get('sqi','?')}, PassRate={s.get('passRate','?')}%, Cut={s.get('cut','?')}, N={s.get('n','?')}"
        for s in stations[:20])
    examiners_txt = "\n".join(
        f"  {e.get('name','?')}: ממוצע={e.get('avg','?')}, פער={e.get('gap','?')}, סטטוס={e.get('status','?')}, N={e.get('n','?')}"
        for e in examiners[:20])

    # Generated report sections
    rpt_interp   = data.get("report_interpretation", "").strip()
    rpt_recs     = data.get("report_recommendations", "").strip()
    rpt_stations = data.get("report_stations", "").strip()
    rpt_examiners= data.get("report_examiners", "").strip()
    rpt_review   = data.get("report_review", "").strip()

    report_block = ""
    if rpt_interp:   report_block += f"\n\n=== פירוש אוטומטי (מהדוח) ===\n{rpt_interp}"
    if rpt_recs:     report_block += f"\n\n=== המלצות אוטומטיות (מהדוח) ===\n{rpt_recs}"
    if rpt_stations: report_block += f"\n\n=== טבלת תחנות (מהדוח) ===\n{rpt_stations}"
    if rpt_examiners:report_block += f"\n\n=== טבלת בוחנים (מהדוח) ===\n{rpt_examiners}"
    if rpt_review:   report_block += f"\n\n=== פריטים לבדיקה (מהדוח) ===\n{rpt_review}"

    PROMPTS = {
        "data_read":
            f"=== נתוני הבחינה (מחושב מהקובץ שהועלה) ===\n{metrics_txt}"
            f"{report_block}\n\nספק סיכום תמציתי של הנתונים הנ\"ל.",
        "reliability":
            f"=== מדדי מהימנות (מחושב מהקובץ) ===\n{metrics_txt}"
            f"{report_block}\n\nפרש את ערכי Alpha, ICC ו-Kappa.",
        "stations":
            f"=== נתוני תחנות (מחושב מהקובץ) ===\n{stations_txt}"
            f"{report_block}\n\nזהה תחנות חלשות וחזקות.",
        "examiners":
            f"=== נתוני בוחנים (מחושב מהקובץ) ===\n{examiners_txt}"
            f"{report_block}\n\nזהה בוחנים הדורשים כיול.",
        "recommendations":
            f"=== נתוני הבחינה המלאים ===\nמדדים:\n{metrics_txt}\nתחנות:\n{stations_txt}\nבוחנים:\n{examiners_txt}"
            f"{report_block}\n\nכתוב 3-5 המלצות פעולה ממוספרות.",
    }

    def _stream():
        for step_id, title, subtitle in OSCE_STEPS:
            prompt = custom_p.get(step_id,"").strip() or PROMPTS[step_id]
            yield f"data: {json.dumps({'type':'step_start','step_id':step_id,'title':title,'subtitle':subtitle},ensure_ascii=False)}\n\n"
            result = ai_call(prompt, system, model_sel)
            yield f"data: {json.dumps({'type':'step_done','step_id':step_id,'content':result},ensure_ascii=False)}\n\n"
        yield 'data: {"type":"done"}\n\n'

    return _cors(Response(_stream(), mimetype="text/event-stream",
        headers={"X-Accel-Buffering":"no","Cache-Control":"no-cache"}))

@app.route("/osce-ai/analyze", methods=["OPTIONS"])
def osce_analyze_opt(): return _cors(Response(""))

# ── OSCE Prep AI ──────────────────────────────────────────────────────────────

PREP_STEPS = [
    ("schedule",      "📅 בוחן סדר יום",         "בדיקת לוח זמנים, תחנות ומשכי זמן"),
    ("questionnaire", "📝 בוחן שאלונים",          "בדיקת שאלוני בוחנים ונבחנים"),
    ("participants",  "👥 בוחן שיבוץ משתתפים",   "בדיקת שיבוץ נבחנים ובוחנים לתחנות"),
    ("scenarios",     "🏥 בוחן תרחישים",          "בדיקת מקרים קליניים ותסריטים"),
    ("final",         "✅ סיכום ואישור מוכנות",   "ניתוח כולל והמלצות לפני הבחינה"),
]

PREP_SYSTEM = """אתה מומחה לניהול בחינות OSCE. בדוק את המסמכים ותן חוות דעת מקצועית.
השתמש אך ורק במידע שסופק. סמן: 🟢 תקין · 🟡 תשומת לב · 🟠 תיקון · 🔴 חסר/קריטי."""

@app.route("/osce-prep/analyze", methods=["POST"])
def prep_analyze():
    data        = request.get_json(force=True) or {}
    custom_p    = data.get("prompts",    {})
    reports     = data.get("reports",    {})
    exam_name   = data.get("examName",   "לא צוין")
    exam_date   = data.get("examDate",   "לא צוין")
    single_step = data.get("singleStep", None)
    system      = custom_p.get("system","").strip() or PREP_SYSTEM
    context     = f"בחינה: {exam_name} · תאריך: {exam_date}\n\n" + \
                  "\n\n".join(f"--- {k} ---\n{v}" for k,v in reports.items() if v)

    steps_to_run = [(sid, t, sub) for sid, t, sub in PREP_STEPS
                    if single_step is None or sid == single_step]

    # Build per-step report snippets (use specific report if available, else full context)
    step_reports = {}
    for step_id, _, _ in steps_to_run:
        if step_id in reports and reports[step_id]:
            step_reports[step_id] = reports[step_id][:4000]
        else:
            step_reports[step_id] = context[:4000]

    def _stream():
        for step_id, title, subtitle in steps_to_run:
            report_snippet = step_reports.get(step_id, context[:4000])
            user_prompt    = custom_p.get(step_id,"").strip()
            # Always include the report data in the prompt
            if user_prompt:
                prompt = f"{user_prompt}\n\n=== דוח הבדיקה ===\n{report_snippet}"
            else:
                prompt = f"בדוק את {title} מהנתונים הבאים:\n\n=== דוח הבדיקה ===\n{report_snippet}"
            yield f"data: {json.dumps({'type':'step_start','step_id':step_id,'title':title,'subtitle':subtitle},ensure_ascii=False)}\n\n"
            result = ai_call(prompt, system)
            yield f"data: {json.dumps({'type':'step_done','step_id':step_id,'content':result},ensure_ascii=False)}\n\n"
        yield 'data: {"type":"done"}\n\n'

    return _cors(Response(_stream(), mimetype="text/event-stream",
        headers={"X-Accel-Buffering":"no","Cache-Control":"no-cache"}))

@app.route("/osce-prep/analyze", methods=["OPTIONS"])
def prep_opt(): return _cors(Response(""))

# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("OSCE_PORT", 5001))
    print(f"OSCE Server running at http://localhost:{port}")
    app.run(debug=True, port=port, threaded=True, use_reloader=True)
