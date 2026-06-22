"""
tutor_agent.py  —  Socratic Pediatric Tutor Agent  (v3)

Architecture
------------
This module implements a ReAct-style agentic loop built on the Anthropic
Messages API with tool use.  The main entry-point is ``chat_stream()``, which:

1. Evaluates five auto-trigger conditions on the current session state.
2. Injects [System: …] hint strings into the user message so Claude follows
   the automated behaviours defined in SYSTEM_PROMPT.
3. Calls the Anthropic API (Sonnet) and iterates through tool-use rounds
   (up to MAX_ITERATIONS) until stop_reason == "end_turn".
4. Yields Server-Sent Event dicts that the Flask route streams to the browser.

Tools (12)
----------
    retrieve_chunks          — RAG search before every question
    validate_student_answer  — LLM-as-judge grading
    compare_sources          — Kliegman vs AAP side-by-side
    give_hint                — nudge after 2 failures
    reveal_answer            — expose full answer after 3 failures
    generate_clinical_case   — synthesise a new patient scenario
    suggest_next_topic       — adaptive learning path
    session_summary          — auto-generated progress report (fires every 5 Qs)
    generate_mcq             — multiple choice question (auto after streak >= 3)
    flag_safety_critical     — red flag / patient safety alerter (auto on low score)
    check_prerequisites      — prerequisite knowledge scaffold (auto on new topic)
    spaced_repetition        — study schedule generator (auto after session_summary)

Auto-triggers (5)
-----------------
    _should_auto_summary        → session_summary   every SUMMARY_EVERY questions
    _should_difficulty_escalate → generate_mcq      streak >= 3
    _should_safety_flag         → flag_safety_critical  score < 35 on safety topic
    _should_check_prerequisites → check_prerequisites   new topic detected
    _should_spaced_repetition   → spaced_repetition     after session_summary
    _should_give_hint           → give_hint             attempt_count >= 2
    _should_reveal_answer       → reveal_answer         attempt_count >= 3

Persistence
-----------
Sessions are saved to disk (``sessions/<sid>.json``) after every chat turn so
they survive server restarts.  ``load_session()`` is called lazily on first
access; ``save_session()`` is called at the end of every ``chat_stream()`` turn.
"""

import os
import sys
import json
import uuid
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

import anthropic
from retrieval import retrieve

# ── Persistence ───────────────────────────────────────────────────────────────

SESSIONS_DIR = Path(__file__).parent.parent / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)


def save_session(sid: str) -> None:
    """Persist a session to disk as ``sessions/<sid>.json``.

    Called at the end of every ``chat_stream()`` turn so sessions survive
    server restarts.  The ``history`` field (which may contain large tool
    result strings) is included so the full conversation context is restored.

    Parameters
    ----------
    sid : str
        Session ID returned by ``new_session()``.
    """
    if sid not in _sessions:
        return
    path = SESSIONS_DIR / f"{sid}.json"
    path.write_text(json.dumps(_sessions[sid], default=str, ensure_ascii=False), encoding="utf-8")


def load_session(sid: str) -> bool:
    """Load a session from disk into ``_sessions`` if not already in memory.

    Called lazily at the start of ``chat_stream()`` so previously saved
    sessions are transparently restored after a server restart.

    Parameters
    ----------
    sid : str
        Session ID to look up.

    Returns
    -------
    bool
        True if the session was found and loaded (or was already in memory),
        False if no saved file exists for this ID.
    """
    if sid in _sessions:
        return True
    path = SESSIONS_DIR / f"{sid}.json"
    if not path.exists():
        return False
    try:
        _sessions[sid] = json.loads(path.read_text(encoding="utf-8"))
        return True
    except Exception:
        return False


def list_sessions() -> list[dict]:
    """Return a summary list of all persisted sessions ordered by creation time.

    Used by the Flask ``/tutor/sessions`` endpoint so the frontend can display
    a session history panel.

    Returns
    -------
    list[dict]
        Each entry contains: sid, created_at, questions_asked, accuracy,
        topics_covered (count), weak_areas (count), difficulty_level.
    """
    summaries = []
    for path in sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            s = json.loads(path.read_text(encoding="utf-8"))
            n = s.get("questions_asked", 0)
            c = s.get("correct_answers", 0)
            summaries.append({
                "sid":             path.stem,
                "created_at":      s.get("created_at", 0),
                "questions_asked": n,
                "accuracy":        round(c / n * 100) if n > 0 else None,
                "topics_count":    len(s.get("topics_covered", [])),
                "weak_count":      len(s.get("weak_areas", [])),
                "difficulty_level": s.get("difficulty_level", "intermediate"),
            })
        except Exception:
            continue
    return summaries


# ── Configuration ─────────────────────────────────────────────────────────────

TUTOR_MODEL = "claude-sonnet-4-6"
JUDGE_MODEL = "claude-haiku-4-5-20251001"
MAX_ITERATIONS = 10
MAX_HISTORY    = 40
SUMMARY_EVERY  = 5   # auto-trigger session_summary every N validated answers

SAFETY_KEYWORDS = {
    "seizure", "meningitis", "torsion", "anaphylaxis", "epiglottitis",
    "sepsis", "shock", "intussusception", "kawasaki", "dka", "ketoacidosis",
}

PEDIATRIC_TOPICS = [
    "febrile seizures", "BRUE / apparent life-threatening event",
    "asthma exacerbation", "acute gastroenteritis / dehydration",
    "bacterial meningitis", "pneumonia in children",
    "kawasaki disease", "intussusception", "pyloric stenosis",
    "neonatal jaundice", "croup vs epiglottitis", "RSV bronchiolitis",
    "anaphylaxis management", "diabetic ketoacidosis pediatric",
    "appendicitis in children", "scrotal pain / testicular torsion",
]

SYSTEM_PROMPT = """\
You are a Socratic pediatric medicine tutor. Students are learning from \
Kliegman's Pediatric Decision-Making Strategies and the AAP Case-Based Guide.

## Teaching rules
1. NEVER give the answer directly when a student asks about a clinical topic.
2. Call retrieve_chunks FIRST — your teaching must be grounded in textbook evidence.
3. Ask exactly ONE focused Socratic question per turn.
4. After the student replies, call validate_student_answer to grade it.
5. After 2 failures: call give_hint.
6. After 3 failures: call reveal_answer then ask the student to explain WHY.
7. Use compare_sources whenever Kliegman and AAP might differ.

## Automated behaviours (you MUST follow these)
- When starting a new topic: call generate_clinical_case to open with a realistic patient.
- Every 5 validated answers: call session_summary to show the student their progress.
- After a student masters a topic (2 consecutive correct answers): call suggest_next_topic.
- After streak >= 3 consecutive correct answers: call generate_mcq to challenge with multiple-choice.
- When student misses a safety-critical point (validate_student_answer score < 35 on emergency topic): call flag_safety_critical.
- When starting a new complex topic for the first time: call check_prerequisites to scaffold learning.
- After session_summary: call spaced_repetition to give the student a personalised review schedule.

## Tone
Encouraging but clinically precise — senior resident on rounds.
Cite sources: (Kliegman p.312) or (AAP p.89).
Responses: 2-3 sentences for questions; fuller for reveals/summaries.\
"""

# ── Tool schemas ───────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "retrieve_chunks",
        "description": (
            "Search Kliegman + AAP textbooks for clinical evidence. "
            "Call BEFORE asking any question."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "k":     {"type": "integer", "default": 4}
            },
            "required": ["query"]
        }
    },
    {
        "name": "validate_student_answer",
        "description": "Grade the student's latest answer (correct/partial/incorrect + score 0-100 + feedback).",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_answer": {"type": "string"},
                "correct_answer": {"type": "string"},
                "criteria":       {"type": "string"}
            },
            "required": ["student_answer", "correct_answer"]
        }
    },
    {
        "name": "compare_sources",
        "description": "Return what Kliegman and AAP each say about a topic to highlight agreements or differences.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"}
            },
            "required": ["topic"]
        }
    },
    {
        "name": "give_hint",
        "description": "Produce a targeted hint after the student has failed twice on the same question.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question":       {"type": "string"},
                "correct_answer": {"type": "string"}
            },
            "required": ["question", "correct_answer"]
        }
    },
    {
        "name": "reveal_answer",
        "description": "Reveal the full evidence-based answer with source citations after 3 failed attempts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "answer":   {"type": "string"}
            },
            "required": ["question", "answer"]
        }
    },
    {
        "name": "generate_clinical_case",
        "description": (
            "Synthesise a new realistic clinical case scenario grounded in retrieved textbook evidence. "
            "Call when starting a new topic to open with a concrete patient."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic":      {"type": "string"},
                "difficulty": {
                    "type": "string",
                    "enum": ["basic", "intermediate", "advanced"],
                    "default": "intermediate"
                }
            },
            "required": ["topic"]
        }
    },
    {
        "name": "suggest_next_topic",
        "description": (
            "Based on covered topics and weak areas, recommend the most valuable next topic to study. "
            "Call after a student masters a topic."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "weak_areas":      {"type": "array",  "items": {"type": "string"}},
                "covered_topics":  {"type": "array",  "items": {"type": "string"}}
            },
            "required": []
        }
    },
    {
        "name": "session_summary",
        "description": (
            "Generate a comprehensive learning-progress report for the current session. "
            "MUST be called automatically every 5 validated answers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "generate_mcq",
        "description": (
            "Generate a 4-option multiple-choice question grounded in retrieved textbook evidence. "
            "Call automatically when the student has a streak of 3 or more correct answers to increase challenge."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "difficulty": {
                    "type": "string",
                    "enum": ["basic", "intermediate", "advanced"],
                    "default": "intermediate"
                }
            },
            "required": ["topic"]
        }
    },
    {
        "name": "flag_safety_critical",
        "description": (
            "Identify and highlight red flags, must-not-miss diagnoses, and immediate safety actions "
            "for an emergency or high-stakes topic. Call when a student scores < 35 on a safety-critical topic."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic":           {"type": "string"},
                "missed_concept":  {"type": "string"}
            },
            "required": ["topic", "missed_concept"]
        }
    },
    {
        "name": "check_prerequisites",
        "description": (
            "Assess whether the student has demonstrated knowledge of prerequisite concepts "
            "before starting a new complex topic. Call on first encounter of a new topic."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic":         {"type": "string"},
                "prerequisites": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["topic", "prerequisites"]
        }
    },
    {
        "name": "spaced_repetition",
        "description": (
            "Create a personalised spaced-repetition study schedule for weak areas and mastered topics. "
            "Call automatically after session_summary to give the student a concrete review plan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "weak_areas":       {"type": "array", "items": {"type": "string"}},
                "mastered_topics":  {"type": "array", "items": {"type": "string"}}
            },
            "required": ["weak_areas", "mastered_topics"]
        }
    },
]

# ── Session store ─────────────────────────────────────────────────────────────

_sessions: dict[str, dict] = {}


def new_session() -> str:
    """Create a new tutor session and return its 8-character ID.

    Initialises all tracking counters to zero/empty so the auto-trigger
    functions start from a clean slate.

    Returns
    -------
    str
        Unique session identifier (first 8 chars of a UUID4).
    """
    sid = str(uuid.uuid4())[:8]
    _sessions[sid] = {
        "history":              [],
        "questions_asked":      0,
        "correct_answers":      0,
        "topics_covered":       [],
        "weak_areas":           [],
        "attempt_count":        0,
        "streak":               0,
        "current_chunks":       [],
        "last_question":        "",
        "last_correct_ans":     "",
        "tool_usage":           {},   # tool_name -> call count
        "last_summary_at":      0,    # questions_asked count when last summary fired
        "last_tool":            "",   # name of most recently called tool
        "last_score":           None, # score from most recent validate_student_answer
        "difficulty_level":     "intermediate",
        "prerequisites_checked": [],  # topics whose prerequisites have been checked
        "created_at":           time.time(),
        "total_input_tokens":   0,    # cumulative input tokens across all API calls
        "total_output_tokens":  0,    # cumulative output tokens across all API calls
        "call_log":             [],   # ordered list of every tool call with params + result
    }
    return sid


def get_session_stats(session_id: str) -> dict:
    """Return a lightweight stats snapshot for the given session.

    Used by the Flask ``/tutor/stats/<session_id>`` endpoint and appended to
    every ``done`` SSE event so the frontend can update its sidebar widgets
    without a separate API call.

    Parameters
    ----------
    session_id : str
        ID returned by ``new_session()``.

    Returns
    -------
    dict
        Keys: questions_asked, correct_answers, accuracy (float|None),
        topics_covered, weak_areas, attempt_count, streak, tool_usage,
        difficulty_level.
    """
    s = _sessions.get(session_id, {})
    n = s.get("questions_asked", 0)
    return {
        "questions_asked": n,
        "correct_answers": s.get("correct_answers", 0),
        "accuracy":        round(s["correct_answers"] / n, 2) if n > 0 else None,
        "topics_covered":  s.get("topics_covered", []),
        "weak_areas":      s.get("weak_areas", []),
        "attempt_count":   s.get("attempt_count", 0),
        "streak":          s.get("streak", 0),
        "tool_usage":          s.get("tool_usage", {}),
        "difficulty_level":    s.get("difficulty_level", "intermediate"),
        "total_input_tokens":  s.get("total_input_tokens", 0),
        "total_output_tokens": s.get("total_output_tokens", 0),
    }


# ── Tool execution ────────────────────────────────────────────────────────────

def _exec_retrieve_chunks(inp: dict, session: dict) -> dict:
    """Execute the ``retrieve_chunks`` tool.

    Searches the FAISS vector index (Kliegman + AAP embeddings) for the most
    relevant text chunks using the fixed-size chunking strategy.

    Side-effects
    ------------
    - Saves retrieved chunks to ``session["current_chunks"]`` so subsequent
      tool calls (compare_sources, generate_clinical_case) can reuse them
      without a second retrieval.

    Parameters
    ----------
    inp : dict
        ``query`` (str) — search string.
        ``k`` (int, optional) — number of chunks to return; clamped to [2, 8].
    session : dict
        Active session state.

    Returns
    -------
    dict
        ``chunks_found`` (int) and ``chunks`` list, each with id, source,
        page, similarity score, and first 400 chars of text.
    """
    query = inp.get("query", "")
    k     = max(2, min(int(inp.get("k", 4)), 8))
    chunks = retrieve(query, k=k, strategy="fixed")
    session["current_chunks"] = chunks
    return {
        "chunks_found": len(chunks),
        "chunks": [
            {
                "id":     c["chunk_id"],
                "source": c["metadata"].get("source", ""),
                "page":   c["metadata"].get("page", ""),
                "score":  round(c["score"], 3),
                "text":   c["text"][:400],
            }
            for c in chunks
        ]
    }


def _exec_validate_answer(inp: dict, session: dict) -> dict:
    """Execute the ``validate_student_answer`` tool (LLM-as-Judge).

    Sends the student's answer and the expected correct answer to the
    JUDGE_MODEL (Haiku) which returns a structured JSON grade.

    Side-effects
    ------------
    - Increments ``session["questions_asked"]``.
    - Updates ``session["streak"]``, ``session["attempt_count"]``,
      ``session["correct_answers"]``, ``session["last_score"]``,
      ``session["difficulty_level"]``, and ``session["weak_areas"]``.

    Parameters
    ----------
    inp : dict
        ``student_answer`` (str), ``correct_answer`` (str),
        ``criteria`` (str, optional).
    session : dict
        Active session state.

    Returns
    -------
    dict
        ``grade`` ("correct"|"partial"|"incorrect"), ``score`` (0-100),
        ``feedback`` (str).
    """
    student_answer = inp.get("student_answer", "")
    correct_answer = inp.get("correct_answer", "")
    criteria       = inp.get("criteria", "")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"grade": "unknown", "score": 50, "feedback": "API key not set."}

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": (
                f'Grade this student answer for a medical exam question.\n\n'
                f'Student answered: "{student_answer}"\n'
                f'Correct answer: "{correct_answer}"\n'
                f'Key criteria: {criteria or "clinical accuracy"}\n\n'
                f'Reply JSON only:\n'
                f'{{"grade":"correct"|"partial"|"incorrect","score":0-100,"feedback":"1-2 sentence feedback"}}'
            )
        }]
    )
    try:
        result = json.loads(resp.content[0].text.strip())
    except Exception:
        result = {"grade": "unknown", "score": 50, "feedback": resp.content[0].text.strip()}

    session["questions_asked"] += 1
    session["last_score"] = result.get("score", 50)
    session["last_tool"] = "validate_student_answer"

    if result.get("grade") == "correct":
        session["correct_answers"] += 1
        session["attempt_count"] = 0
        session["streak"] = session.get("streak", 0) + 1
        if session["streak"] >= 3:
            session["difficulty_level"] = "advanced"
    else:
        session["attempt_count"] = session.get("attempt_count", 0) + 1
        session["streak"] = 0
        topic = session.get("last_question", "")
        if topic and topic not in session.get("weak_areas", []):
            session.setdefault("weak_areas", []).append(topic)

    return result


def _exec_compare_sources(inp: dict, session: dict) -> dict:
    """Execute the ``compare_sources`` tool.

    Retrieves up to 8 chunks for the topic and splits them by source
    (Kliegman vs AAP) so the tutor can highlight agreements or contradictions
    between the two textbooks.

    Parameters
    ----------
    inp : dict
        ``topic`` (str) — clinical topic to compare.
    session : dict
        Active session state (unused but kept for interface consistency).

    Returns
    -------
    dict
        ``kliegman`` (list of up to 2 excerpts), ``aap`` (list of up to 2
        excerpts), ``agreement`` (str summary).
    """
    topic  = inp.get("topic", "")
    chunks = retrieve(topic, k=8, strategy="fixed")
    kliegman, aap = [], []
    for c in chunks:
        src = (c["metadata"].get("source", "") + c["chunk_id"]).lower()
        entry = {
            "text":  c["text"][:350],
            "page":  c["metadata"].get("page", ""),
            "score": round(c["score"], 3),
        }
        if "kliegman" in src:
            kliegman.append(entry)
        elif "aap" in src or "case" in src:
            aap.append(entry)
    return {
        "kliegman": kliegman[:2],
        "aap":      aap[:2],
        "agreement": "Both sources align." if kliegman and aap else "Only one source found.",
    }


def _exec_give_hint(inp: dict, session: dict) -> dict:
    """Execute the ``give_hint`` tool.

    Generates a lightweight hint by exposing the first third of the correct
    answer (word count). Does NOT call the LLM — purely rule-based to keep
    latency and cost low.

    Parameters
    ----------
    inp : dict
        ``question`` (str), ``correct_answer`` (str).
    session : dict
        Active session state; falls back to ``session["last_correct_ans"]``
        if correct_answer is missing from inp.

    Returns
    -------
    dict
        ``hint`` (str) — a "Think about: …" phrase.
    """
    correct_answer = inp.get("correct_answer", session.get("last_correct_ans", ""))
    words = correct_answer.split()
    hint  = " ".join(words[:max(3, len(words) // 3)]) + "..."
    return {"hint": f"Think about: {hint}"}


def _exec_reveal_answer(inp: dict, session: dict) -> dict:
    """Execute the ``reveal_answer`` tool.

    Called after 3 consecutive failures.  Resets attempt_count and streak
    so the session can cleanly move to the next question.

    Parameters
    ----------
    inp : dict
        ``question`` (str), ``answer`` (str).
    session : dict
        Active session state.

    Returns
    -------
    dict
        ``revealed`` (True), ``question``, ``answer``.
    """
    session["attempt_count"] = 0
    session["streak"] = 0
    return {
        "revealed": True,
        "question": inp.get("question", ""),
        "answer":   inp.get("answer", ""),
    }


def _exec_generate_case(inp: dict, session: dict) -> dict:
    """Execute the ``generate_clinical_case`` tool.

    Uses JUDGE_MODEL (Haiku) to synthesise a realistic pediatric case scenario
    grounded in RAG-retrieved textbook evidence.  The case includes patient
    demographics, history, vitals, and exam findings — but deliberately omits
    the diagnosis to preserve the Socratic structure.

    Parameters
    ----------
    inp : dict
        ``topic`` (str) — clinical topic for the case.
        ``difficulty`` ("basic"|"intermediate"|"advanced").
    session : dict
        Active session state (unused).

    Returns
    -------
    dict
        ``case`` (str formatted case text), ``topic``, ``difficulty``,
        ``sources`` (list of chunk IDs and pages used as evidence).
    """
    topic      = inp.get("topic", "")
    difficulty = inp.get("difficulty", "intermediate")
    chunks     = retrieve(topic, k=5, strategy="fixed")
    context    = "\n\n".join(c["text"][:300] for c in chunks[:3])

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"error": "API key not set"}

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": (
                f"Create a {difficulty} pediatric clinical case scenario about: {topic}.\n"
                f"Base it ONLY on this textbook evidence:\n{context}\n\n"
                f"Format:\n"
                f"Patient: [age, sex, chief complaint]\n"
                f"History: [2-3 sentences]\n"
                f"Vitals: [relevant vitals]\n"
                f"Exam: [key findings]\n"
                f"Keep it realistic and clinically precise. No diagnosis yet."
            )
        }]
    )
    case_text = resp.content[0].text.strip()
    return {
        "case":       case_text,
        "topic":      topic,
        "difficulty": difficulty,
        "sources":    [{"id": c["chunk_id"], "page": c["metadata"].get("page", "")} for c in chunks[:2]],
    }


def _exec_suggest_next_topic(inp: dict, session: dict) -> dict:
    """Execute the ``suggest_next_topic`` tool.

    Applies a simple prioritisation rule:
    1. If the student has weak areas, revisit the first one.
    2. Otherwise, suggest the first uncovered topic from PEDIATRIC_TOPICS.
    3. If everything is covered, recommend review of the last studied topic.

    Parameters
    ----------
    inp : dict
        ``weak_areas`` (list, optional), ``covered_topics`` (list, optional).
        Falls back to session values if not provided.
    session : dict
        Active session state.

    Returns
    -------
    dict
        ``suggested_topic`` (str), ``reason`` (str), ``weak_areas`` (list),
        ``covered_count`` (int), ``remaining_count`` (int).
    """
    weak    = inp.get("weak_areas",     session.get("weak_areas",    []))
    covered = inp.get("covered_topics", session.get("topics_covered", []))

    if weak:
        suggestion = weak[0]
        reason     = "You struggled with this topic — worth revisiting."
    else:
        remaining = [t for t in PEDIATRIC_TOPICS
                     if not any(t.lower() in c.lower() for c in covered)]
        if remaining:
            suggestion = remaining[0]
            reason     = "This is a high-yield topic you haven't covered yet."
        else:
            suggestion = covered[-1] if covered else "febrile seizures"
            reason     = "You've covered the core curriculum — review for depth."

    return {
        "suggested_topic": suggestion,
        "reason":          reason,
        "weak_areas":      weak[:3],
        "covered_count":   len(set(covered)),
        "remaining_count": len(PEDIATRIC_TOPICS) - len(set(covered)),
    }


def _exec_session_summary(inp: dict, session: dict) -> dict:
    """Execute the ``session_summary`` tool.

    Computes accuracy, streak, and a qualitative verdict, then records
    ``last_summary_at`` so the auto-trigger does not fire again for the same
    question count.

    Parameters
    ----------
    inp : dict
        Empty (no parameters required).
    session : dict
        Active session state.

    Returns
    -------
    dict
        ``questions_answered``, ``correct``, ``accuracy_pct``, ``streak``,
        ``topics_covered``, ``weak_areas`` (up to 5), ``verdict`` (str).
    """
    n       = session.get("questions_asked", 0)
    correct = session.get("correct_answers", 0)
    acc     = round(correct / n * 100) if n > 0 else 0
    weak    = session.get("weak_areas",    [])
    topics  = session.get("topics_covered", [])
    streak  = session.get("streak", 0)

    if acc >= 80:
        verdict = "Excellent performance! You're demonstrating strong clinical reasoning."
    elif acc >= 60:
        verdict = "Good progress. Focus on the weak areas below to solidify your understanding."
    else:
        verdict = "Keep going — each question is building your clinical framework."

    session["last_summary_at"] = n

    return {
        "questions_answered": n,
        "correct":            correct,
        "accuracy_pct":       acc,
        "streak":             streak,
        "topics_covered":     topics,
        "weak_areas":         weak[:5],
        "verdict":            verdict,
    }


def _exec_generate_mcq(inp: dict, session: dict) -> dict:
    """Execute the ``generate_mcq`` tool.

    Asks JUDGE_MODEL (Haiku) to produce a 4-option MCQ grounded in
    RAG-retrieved evidence.  The returned JSON includes the question, four
    options (A-D), the correct key, an explanation, and a source reference.

    Auto-triggered when ``streak >= 3`` to escalate challenge level.

    Parameters
    ----------
    inp : dict
        ``topic`` (str), ``difficulty`` ("basic"|"intermediate"|"advanced").
    session : dict
        Active session state; provides topic and difficulty fallbacks.

    Returns
    -------
    dict
        ``question``, ``options`` ({A,B,C,D}), ``correct`` (letter),
        ``explanation``, ``source``.
    """
    topic      = inp.get("topic", session.get("last_question", "pediatrics"))
    difficulty = inp.get("difficulty", session.get("difficulty_level", "intermediate"))
    chunks     = retrieve(topic, k=5, strategy="fixed")
    context    = "\n\n".join(c["text"][:300] for c in chunks[:3])
    source_ref = chunks[0]["metadata"].get("source", "Kliegman") + " p." + str(chunks[0]["metadata"].get("page", "")) if chunks else "Kliegman"

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"error": "API key not set"}

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": (
                f"Create a {difficulty} 4-option multiple-choice question about: {topic}.\n"
                f"Base it ONLY on this textbook evidence:\n{context}\n\n"
                f"Reply with JSON only (no markdown):\n"
                f'{{"question":"...","options":{{"A":"...","B":"...","C":"...","D":"..."}},'
                f'"correct":"A"|"B"|"C"|"D","explanation":"1-2 sentences why correct",'
                f'"source":"{source_ref}"}}'
            )
        }]
    )
    try:
        result = json.loads(resp.content[0].text.strip())
    except Exception:
        result = {
            "question": f"Which of the following is most characteristic of {topic}?",
            "options": {"A": "Option A", "B": "Option B", "C": "Option C", "D": "Option D"},
            "correct": "A",
            "explanation": resp.content[0].text.strip()[:200],
            "source": source_ref,
        }
    return result


def _exec_flag_safety_critical(inp: dict, session: dict) -> dict:
    """Execute the ``flag_safety_critical`` tool.

    Retrieves red-flag evidence from the vector store and asks JUDGE_MODEL to
    identify the most dangerous missed diagnosis and the immediate clinical
    action a clinician must take.

    Falls back to a hard-coded rule-based response if the API key is missing,
    ensuring the safety alert always fires even in offline/test environments.

    Auto-triggered when ``last_score < 35`` AND the topic contains a
    SAFETY_KEYWORDS term.

    Parameters
    ----------
    inp : dict
        ``topic`` (str), ``missed_concept`` (str).
    session : dict
        Active session state (unused).

    Returns
    -------
    dict
        ``alert_level`` ("red"|"orange"), ``red_flags`` (list of str),
        ``must_not_miss`` (str), ``immediate_action`` (str), ``evidence`` (str).
    """
    topic          = inp.get("topic", "")
    missed_concept = inp.get("missed_concept", "")
    chunks         = retrieve(f"{topic} red flags emergency signs", k=6, strategy="fixed")
    context        = "\n\n".join(c["text"][:300] for c in chunks[:4])
    evidence_ref   = chunks[0]["metadata"].get("source", "Kliegman") + " p." + str(chunks[0]["metadata"].get("page", "")) if chunks else ""

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {
            "alert_level": "red",
            "red_flags": ["Altered mental status", "Hemodynamic instability", "Respiratory failure"],
            "must_not_miss": topic,
            "immediate_action": "Stabilise ABCs, call senior, consider emergency transfer.",
            "evidence": evidence_ref,
        }

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": (
                f"For the pediatric topic '{topic}', the student missed: '{missed_concept}'.\n"
                f"Using this evidence:\n{context}\n\n"
                f"Identify the most critical safety concerns. Reply JSON only:\n"
                f'{{"alert_level":"red"|"orange","red_flags":["...","...","..."],'
                f'"must_not_miss":"single most dangerous missed diagnosis",'
                f'"immediate_action":"what a clinician must do immediately",'
                f'"evidence":"{evidence_ref}"}}'
            )
        }]
    )
    try:
        result = json.loads(resp.content[0].text.strip())
    except Exception:
        result = {
            "alert_level": "red",
            "red_flags": ["Altered mental status", "Haemodynamic instability", "Respiratory compromise"],
            "must_not_miss": topic,
            "immediate_action": "Assess ABCs immediately. Escalate to senior clinician.",
            "evidence": evidence_ref,
        }
    return result


def _exec_check_prerequisites(inp: dict, session: dict) -> dict:
    """Execute the ``check_prerequisites`` tool.

    Scans the existing conversation history for evidence that the student has
    already demonstrated knowledge of each prerequisite concept.  No LLM call
    is made — matching is done with simple substring search on the flattened
    history text.

    Status classification per concept:
    - ``known``   — concept string found verbatim in history.
    - ``unclear`` — at least one word (>4 chars) from the concept found.
    - ``unknown`` — no evidence found.

    Auto-triggered the first time each new topic appears in topics_covered.

    Parameters
    ----------
    inp : dict
        ``topic`` (str), ``prerequisites`` (list of str concept labels).
    session : dict
        Active session state; history is read from ``session["history"]``.

    Returns
    -------
    dict
        ``topic``, ``prerequisites`` (list of {concept, status}),
        ``recommendation`` (str action for the tutor).
    """
    topic         = inp.get("topic", "")
    prerequisites = inp.get("prerequisites", [])

    history_text = " ".join(
        block.get("content", "") if isinstance(block.get("content"), str)
        else " ".join(
            b.get("text", "") for b in block.get("content", [])
            if isinstance(b, dict) and b.get("type") == "text"
        )
        for block in session.get("history", [])
        if isinstance(block, dict)
    ).lower()

    prereq_statuses = []
    for concept in prerequisites:
        c_lower = concept.lower()
        if c_lower in history_text:
            status = "known"
        elif any(word in history_text for word in c_lower.split() if len(word) > 4):
            status = "unclear"
        else:
            status = "unknown"
        prereq_statuses.append({"concept": concept, "status": status})

    unknown_count = sum(1 for p in prereq_statuses if p["status"] == "unknown")
    unclear_count = sum(1 for p in prereq_statuses if p["status"] == "unclear")

    if unknown_count == 0 and unclear_count == 0:
        recommendation = f"Student appears ready for {topic}. All prerequisites demonstrated."
    elif unknown_count > 0:
        missing = [p["concept"] for p in prereq_statuses if p["status"] == "unknown"]
        recommendation = f"Review {', '.join(missing[:2])} before diving into {topic}."
    else:
        recommendation = f"Student has partial prerequisite knowledge — proceed carefully with {topic}."

    session.setdefault("prerequisites_checked", [])
    if topic not in session["prerequisites_checked"]:
        session["prerequisites_checked"].append(topic)

    return {
        "topic":          topic,
        "prerequisites":  prereq_statuses,
        "recommendation": recommendation,
    }


def _exec_spaced_repetition(inp: dict, session: dict) -> dict:
    """Execute the ``spaced_repetition`` tool.

    Generates a personalised review schedule using the SM-2-inspired
    intervals: weak areas at 1/3/7 days (high priority) and mastered topics
    at 7/21 days (low priority).  No LLM call — purely algorithmic.

    Auto-triggered immediately after ``session_summary`` fires.

    Parameters
    ----------
    inp : dict
        ``weak_areas`` (list), ``mastered_topics`` (list).
        Falls back to session values if not provided.
    session : dict
        Active session state.

    Returns
    -------
    dict
        ``schedule`` (list of {topic, review_in, priority}),
        ``total_topics`` (int), ``message`` (str motivational text).
    """
    weak_areas      = inp.get("weak_areas",      session.get("weak_areas", []))
    mastered_topics = inp.get("mastered_topics",  [t for t in session.get("topics_covered", [])
                                                   if t not in session.get("weak_areas", [])])

    schedule = []

    for topic in weak_areas[:4]:
        schedule.append({"topic": topic, "review_in": "1 day",  "priority": "high"})
        schedule.append({"topic": topic, "review_in": "3 days", "priority": "high"})
        schedule.append({"topic": topic, "review_in": "7 days", "priority": "medium"})

    for topic in mastered_topics[:4]:
        schedule.append({"topic": topic, "review_in": "7 days",  "priority": "low"})
        schedule.append({"topic": topic, "review_in": "21 days", "priority": "low"})

    total = len(set(weak_areas[:4]) | set(mastered_topics[:4]))

    if weak_areas:
        message = (f"Focus on your {len(weak_areas[:4])} weak area(s) first. "
                   f"Review them at 1-, 3-, and 7-day intervals for maximum retention.")
    else:
        message = "Great work — no weak areas! Maintain your mastered topics with 7- and 21-day reviews."

    return {
        "schedule":     schedule,
        "total_topics": total,
        "message":      message,
    }


_TOOL_MAP = {
    "retrieve_chunks":         _exec_retrieve_chunks,
    "validate_student_answer": _exec_validate_answer,
    "compare_sources":         _exec_compare_sources,
    "give_hint":               _exec_give_hint,
    "reveal_answer":           _exec_reveal_answer,
    "generate_clinical_case":  _exec_generate_case,
    "suggest_next_topic":      _exec_suggest_next_topic,
    "session_summary":         _exec_session_summary,
    "generate_mcq":            _exec_generate_mcq,
    "flag_safety_critical":    _exec_flag_safety_critical,
    "check_prerequisites":     _exec_check_prerequisites,
    "spaced_repetition":       _exec_spaced_repetition,
}


def _execute_tool(name: str, inp: dict, session: dict) -> dict:
    """Dispatch a tool call by name and record usage statistics.

    Looks up the tool handler in ``_TOOL_MAP``, increments the per-tool call
    counter in ``session["tool_usage"]``, and catches any exception so a
    single failing tool never crashes the agentic loop.

    Parameters
    ----------
    name : str
        Tool name as returned by the API (must match a key in _TOOL_MAP).
    inp : dict
        Tool input parameters provided by the model.
    session : dict
        Active session state passed through to the handler.

    Returns
    -------
    dict
        Tool result, or ``{"error": "<message>"}`` if the handler raised.
    """
    fn = _TOOL_MAP.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    session.setdefault("tool_usage", {})[name] = \
        session["tool_usage"].get(name, 0) + 1
    session["last_tool"] = name
    try:
        return fn(inp, session)
    except Exception as e:
        return {"error": str(e)}


def _content_to_dicts(content) -> list:
    """Convert the Anthropic SDK content block objects to plain dicts.

    The Messages API returns typed objects (TextBlock, ToolUseBlock).  This
    function normalises them to JSON-serialisable dicts so they can be stored
    in ``session["history"]`` and re-sent as context in subsequent API calls.

    Parameters
    ----------
    content : list
        List of content block objects from ``response.content``.

    Returns
    -------
    list
        List of dicts with ``type`` key; text blocks also have ``text``,
        tool_use blocks also have ``id``, ``name``, ``input``.
    """
    out = []
    for block in content:
        if block.type == "text":
            out.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            out.append({
                "type":  "tool_use",
                "id":    block.id,
                "name":  block.name,
                "input": block.input,
            })
    return out


# ── Auto-trigger logic ────────────────────────────────────────────────────────

def _should_auto_summary(session: dict) -> bool:
    """Return True when it is time to fire an automatic session_summary.

    Fires when ``questions_asked`` is a non-zero multiple of SUMMARY_EVERY
    AND a summary has not already been generated for this exact count
    (prevents double-firing on the same question).

    Parameters
    ----------
    session : dict
        Active session state.
    """
    n    = session.get("questions_asked", 0)
    last = session.get("last_summary_at", 0)
    return n > 0 and n % SUMMARY_EVERY == 0 and n != last


def _should_difficulty_escalate(session: dict) -> bool:
    """Return True when the student should receive an MCQ challenge.

    Condition: streak >= 3 AND the most recently executed tool was
    ``validate_student_answer`` (ensures we only escalate immediately after
    a graded answer, not mid-turn).

    Parameters
    ----------
    session : dict
        Active session state.
    """
    return (session.get("streak", 0) >= 3
            and session.get("last_tool", "") == "validate_student_answer")


def _should_safety_flag(session: dict) -> bool:
    """Return True when a safety-critical alert must be raised.

    Condition: the last tool was ``validate_student_answer``, the score was
    below 35, AND the current topic contains at least one SAFETY_KEYWORDS term.

    Parameters
    ----------
    session : dict
        Active session state.
    """
    if session.get("last_tool", "") != "validate_student_answer":
        return False
    score = session.get("last_score")
    if score is None or score >= 35:
        return False
    topic = session.get("last_question", "").lower()
    return any(kw in topic for kw in SAFETY_KEYWORDS)


def _should_check_prerequisites(session: dict) -> bool:
    """Return True when a new topic needs its prerequisites checked.

    Fires the first time each topic appears in ``topics_covered`` (i.e. has
    not yet been added to ``prerequisites_checked``).

    Parameters
    ----------
    session : dict
        Active session state.
    """
    topics   = session.get("topics_covered", [])
    checked  = session.get("prerequisites_checked", [])
    if not topics:
        return False
    latest = topics[-1]
    return latest not in checked


def _should_spaced_repetition(session: dict) -> bool:
    """Return True when a spaced-repetition schedule should be generated.

    Fires immediately after ``session_summary`` is called, so the student
    always receives a concrete review plan following their progress report.

    Parameters
    ----------
    session : dict
        Active session state.
    """
    return session.get("last_tool", "") == "session_summary"


def _should_give_hint(session: dict) -> bool:
    """Return True when the student needs a hint injected into the prompt.

    Fires when attempt_count >= 2 so the model is explicitly instructed to
    call give_hint with the last known correct answer, rather than relying on
    the system prompt alone.

    Parameters
    ----------
    session : dict
        Active session state.
    """
    return session.get("attempt_count", 0) >= 2


def _should_reveal_answer(session: dict) -> bool:
    """Return True when the full answer should be revealed.

    Fires when attempt_count >= 3 — three consecutive failures on the same
    question warrant exposing the evidence-based answer.

    Parameters
    ----------
    session : dict
        Active session state.
    """
    return session.get("attempt_count", 0) >= 3


# ── Public chat_stream ────────────────────────────────────────────────────────

def chat_stream(session_id: str, user_message: str):
    """Main agentic loop — process one student message and stream events.

    This is a Python generator.  Each ``yield`` emits one SSE event dict that
    the Flask route serialises to ``data: <json>\\n\\n`` and streams to the
    browser via Server-Sent Events.

    Algorithm
    ---------
    1. Evaluate all five auto-trigger predicates.
    2. If any trigger fires, append a [System: …] instruction to the user
       message and yield an ``auto_trigger`` event.
    3. Append the (possibly augmented) message to history.
    4. Enter the ReAct loop (up to MAX_ITERATIONS):
       a. Call the Anthropic Messages API with full history + TOOLS.
       b. Yield ``text`` events for any TextBlocks.
       c. If stop_reason == "end_turn", break.
       d. For each ToolUseBlock: yield ``tool_start``, execute the tool,
          yield ``tool_result``, and accumulate results.
       e. Append tool results as a user turn and loop.
    5. Yield a ``done`` event with session statistics.

    SSE event types
    ---------------
    ``text``         — assistant text fragment.
    ``tool_start``   — tool name + input (before execution).
    ``tool_result``  — tool name + result dict (after execution).
    ``auto_trigger`` — which auto-trigger fired and why.
    ``done``         — session statistics snapshot.

    Parameters
    ----------
    session_id : str
        ID from ``new_session()``; a new session is created if not found.
    user_message : str
        Raw text typed by the student.

    Yields
    ------
    dict
        SSE event dicts described above.
    """
    if session_id not in _sessions:
        if not load_session(session_id):
            session_id = new_session()

    session = _sessions[session_id]
    history = session["history"]

    # ── Collect all auto-trigger injections ──────────────────────────────────
    msg = user_message
    hints = []

    if _should_auto_summary(session):
        hints.append(
            f"[System: You must now call session_summary — "
            f"the student has answered {session['questions_asked']} questions.]"
        )
        yield {"type": "auto_trigger", "tool": "session_summary",
               "reason": f"Auto-fired after {session['questions_asked']} questions"}

    if _should_difficulty_escalate(session):
        topic = session.get("last_question", "the current topic")
        hints.append(
            f"[System: The student has a streak of {session['streak']} correct answers. "
            f"Call generate_mcq with topic='{topic}' and difficulty='advanced' "
            f"to increase the challenge.]"
        )
        yield {"type": "auto_trigger", "tool": "generate_mcq",
               "reason": f"Streak {session['streak']} — escalating to MCQ challenge"}

    if _should_safety_flag(session):
        topic   = session.get("last_question", "the current topic")
        score   = session.get("last_score", 0)
        hints.append(
            f"[System: SAFETY ALERT — student scored {score}/100 on '{topic}', "
            f"which is a safety-critical topic. "
            f"Call flag_safety_critical with topic='{topic}' and missed_concept='low score on emergency topic'.]"
        )
        yield {"type": "auto_trigger", "tool": "flag_safety_critical",
               "reason": f"Score {score} < 35 on safety-critical topic: {topic}"}

    if _should_check_prerequisites(session):
        new_topic = session["topics_covered"][-1]
        hints.append(
            f"[System: The student has just started a new topic: '{new_topic}'. "
            f"Call check_prerequisites with topic='{new_topic}' and a list of relevant "
            f"prerequisite concepts before proceeding.]"
        )
        yield {"type": "auto_trigger", "tool": "check_prerequisites",
               "reason": f"New topic detected: {new_topic}"}

    if _should_spaced_repetition(session):
        weak     = session.get("weak_areas", [])
        mastered = [t for t in session.get("topics_covered", []) if t not in weak]
        hints.append(
            f"[System: session_summary just completed. "
            f"Call spaced_repetition with weak_areas={weak[:4]} and "
            f"mastered_topics={mastered[:4]} to give the student a review schedule.]"
        )
        yield {"type": "auto_trigger", "tool": "spaced_repetition",
               "reason": "Auto-fired after session_summary"}

    if _should_reveal_answer(session):
        question   = session.get("last_question", "the current question")
        correct    = session.get("last_correct_ans", "")
        hints.append(
            f"[System: The student has failed {session['attempt_count']} times on "
            f"'{question}'. You MUST call reveal_answer now with "
            f"question='{question}' and answer='{correct}', then ask them to explain WHY.]"
        )
        yield {"type": "auto_trigger", "tool": "reveal_answer",
               "reason": f"attempt_count={session['attempt_count']} — revealing answer"}
    elif _should_give_hint(session):
        question   = session.get("last_question", "the current question")
        correct    = session.get("last_correct_ans", "")
        hints.append(
            f"[System: The student has failed {session['attempt_count']} times on "
            f"'{question}'. You MUST call give_hint now with "
            f"question='{question}' and correct_answer='{correct}'.]"
        )
        yield {"type": "auto_trigger", "tool": "give_hint",
               "reason": f"attempt_count={session['attempt_count']} — giving hint"}

    if hints:
        msg = user_message + "\n\n" + "\n".join(hints)

    history.append({"role": "user", "content": msg})
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
        session["history"] = history

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        yield {"type": "text", "text": "Error: ANTHROPIC_API_KEY is not set."}
        yield {"type": "done", "session": get_session_stats(session_id)}
        return

    client = anthropic.Anthropic(api_key=api_key)

    for _ in range(MAX_ITERATIONS):
        response = client.messages.create(
            model=TUTOR_MODEL,
            system=SYSTEM_PROMPT,
            messages=history,
            tools=TOOLS,
            max_tokens=1024,
        )

        history.append({
            "role":    "assistant",
            "content": _content_to_dicts(response.content),
        })

        # ── Token accounting ──────────────────────────────────────────────────
        in_tok  = getattr(response.usage, "input_tokens",  0)
        out_tok = getattr(response.usage, "output_tokens", 0)
        session["total_input_tokens"]  = session.get("total_input_tokens",  0) + in_tok
        session["total_output_tokens"] = session.get("total_output_tokens", 0) + out_tok
        yield {
            "type":          "usage",
            "input_tokens":  in_tok,
            "output_tokens": out_tok,
            "total_input":   session["total_input_tokens"],
            "total_output":  session["total_output_tokens"],
        }

        for block in response.content:
            if block.type == "text" and block.text.strip():
                yield {"type": "text", "text": block.text}

        if response.stop_reason == "end_turn":
            break

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            if block.name == "validate_student_answer":
                session["last_correct_ans"] = block.input.get("correct_answer", "")
            if block.name in ("retrieve_chunks", "give_hint", "reveal_answer",
                              "generate_clinical_case", "generate_mcq",
                              "flag_safety_critical", "check_prerequisites"):
                session["last_question"] = block.input.get(
                    "question", block.input.get("query", block.input.get("topic", "")))

            yield {"type": "tool_start", "tool": block.name, "input": block.input}

            t_start = time.time()
            result  = _execute_tool(block.name, block.input, session)
            elapsed = round(time.time() - t_start, 3)

            if block.name == "retrieve_chunks":
                q = block.input.get("query", "")
                if q and q not in session["topics_covered"]:
                    session["topics_covered"].append(q)

            # ── Append to call log ────────────────────────────────────────────
            session.setdefault("call_log", []).append({
                "ts":      round(time.time(), 3),
                "tool":    block.name,
                "params":  block.input,
                "result":  result,
                "elapsed": elapsed,
            })

            yield {"type": "tool_result", "tool": block.name, "result": result}

            tool_results.append({
                "type":        "tool_result",
                "tool_use_id": block.id,
                "content":     json.dumps(result),
            })

        if tool_results:
            history.append({"role": "user", "content": tool_results})

    save_session(session_id)
    yield {"type": "done", "session": get_session_stats(session_id)}
