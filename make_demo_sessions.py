"""
Generate demo sessions that showcase all 12 tools and 7 automations.

Tools:  retrieve_chunks, validate_student_answer, compare_sources, give_hint,
        reveal_answer, generate_clinical_case, suggest_next_topic,
        session_summary, generate_mcq, flag_safety_critical,
        check_prerequisites, spaced_repetition

Automations:
  1. retrieve_chunks  — auto before every question
  2. validate_student_answer — auto after every student response
  3. give_hint        — auto after 2 failed attempts
  4. reveal_answer    — auto after 3 failed attempts
  5. session_summary  — auto after every 5 questions
  6. suggest_next_topic — auto after session_summary
  7. spaced_repetition  — auto after session_summary
"""

import json, time, uuid
from pathlib import Path

SESSIONS_DIR = Path(__file__).parent / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)

NOW = time.time()
DAY = 86400

# ── helpers ───────────────────────────────────────────────────────────────────

def tid():
    return "toolu_" + str(uuid.uuid4())[:12]

def text_block(text):
    return {"type": "text", "text": text}

def tool_use_block(name, input_data, tool_id=None):
    return {"type": "tool_use", "id": tool_id or tid(), "name": name, "input": input_data}

def tool_result_block(tool_id, result):
    return {"type": "tool_result", "tool_use_id": tool_id,
            "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

def user_msg(text):
    return {"role": "user", "content": [text_block(text)]}

def user_tool_result(tool_id, result):
    return {"role": "user", "content": [tool_result_block(tool_id, result)]}

def asst_text(text):
    return {"role": "assistant", "content": [text_block(text)]}

def asst_tool(text, tool_name, tool_input, tool_id=None):
    tid_ = tool_id or tid()
    blocks = []
    if text:
        blocks.append(text_block(text))
    blocks.append(tool_use_block(tool_name, tool_input, tid_))
    return {"role": "assistant", "content": blocks}, tid_


# ════════════════════════════════════════════════════════════════════════════════
# SESSION 1 — "מסלול מלא": retrieve → validate → give_hint → reveal_answer
#              + check_prerequisites + flag_safety_critical + suggest_next_topic
# ════════════════════════════════════════════════════════════════════════════════

def build_session1():
    h = []

    # Turn 1: user asks, agent retrieves then asks question
    h.append(user_msg("אני רוצה ללמוד על חום בתינוקות"))

    t1 = tid()
    h.append({"role": "assistant", "content": [
        text_block("מצוין! לפני שאשאל אותך שאלה, אני אביא חומר רלוונטי מהספר."),
        tool_use_block("retrieve_chunks", {"query": "fever in neonates management", "k": 4}, t1)
    ]})
    h.append(user_tool_result(t1, {
        "chunks_found": 4,
        "chunks": [
            {"id": "klieg_p45_c1", "source": "Kliegman", "page": 45, "score": 0.91,
             "text": "Fever in neonates <3 months requires full sepsis workup including CBC, blood culture, UA, and LP..."},
            {"id": "aap_p12_c2", "source": "AAP Guidelines", "page": 12, "score": 0.87,
             "text": "Rochester criteria define low-risk febrile infants: previously healthy, no focal infection, WBC 5-15k..."},
            {"id": "klieg_p47_c3", "source": "Kliegman", "page": 47, "score": 0.83,
             "text": "Temperature >38°C in infant 0-28 days mandates hospitalization regardless of clinical appearance..."},
            {"id": "aap_p15_c4", "source": "AAP Guidelines", "page": 15, "score": 0.79,
             "text": "Step-by-step management: assess toxicity, obtain cultures, start empiric antibiotics..."}
        ]
    }))

    # AUTO: check_prerequisites
    t2 = tid()
    h.append({"role": "assistant", "content": [
        text_block("תחילה אבדוק שיש לך את הבסיס הנדרש לנושא זה."),
        tool_use_block("check_prerequisites", {"topic": "febrile neonate management", "prerequisites": ["basic immunology", "vital signs interpretation"]}, t2)
    ]})
    h.append(user_tool_result(t2, {
        "topic": "febrile neonate management",
        "prerequisites_met": True,
        "details": "Student has covered basic immunology and vital signs. Ready to proceed."
    }))

    h.append(asst_text("מצוין, יש לך את הבסיס הנדרש! שאלה: תינוק בן שבועיים עם חום 38.5°C — מה הפרוטוקול המלא?"))

    # Turn 2: student wrong answer → validate → give_hint (auto after 1 fail... let's say this is attempt 2)
    h.append(user_msg("לתת אנטיביוטיקה ולשחרר הביתה"))

    t3 = tid()
    h.append({"role": "assistant", "content": [
        text_block(""),
        tool_use_block("validate_student_answer", {
            "question": "תינוק בן שבועיים עם חום 38.5C — מה הפרוטוקול המלא?",
            "student_answer": "לתת אנטיביוטיקה ולשחרר הביתה",
            "correct_answer": "אשפוז, sepsis workup מלא, אנטיביוטיקה IV"
        }, t3)
    ]})
    h.append(user_tool_result(t3, {
        "grade": "incorrect", "score": 15,
        "feedback": "שחרור הביתה אינו מתאים לתינוק מתחת לגיל חודש עם חום. נדרש אשפוז ובירור מלא.",
        "correct_answer": "אשפוז + sepsis workup מלא (CBC, תרביות דם, שתן, LP) + אנטיביוטיקה IV"
    }))

    # AUTO: give_hint (attempt 2)
    t4 = tid()
    h.append({"role": "assistant", "content": [
        text_block("[System: Student failed 2 times. Giving hint now.]"),
        tool_use_block("give_hint", {
            "question": "תינוק בן שבועיים עם חום 38.5C — מה הפרוטוקול המלא?",
            "correct_answer": "אשפוז, sepsis workup מלא, אנטיביוטיקה IV"
        }, t4)
    ]})
    h.append(user_tool_result(t4, {
        "hint": "💡 חשוב: תינוק מתחת לגיל חודש הוא מקרה מיוחד. מערכת החיסון שלו לא בשלה. מה דורשת הגישה 'rule out sepsis'?"
    }))

    h.append(asst_text("לא בדיוק. רמז: תינוק מתחת לגיל חודש — אי אפשר לשחרר הביתה עם חום. מה בדרך כלל עושים כשחושדים בספסיס?"))

    # Turn 3: still wrong → reveal_answer (auto after 3 fails)
    h.append(user_msg("ממש לא בטוח... בדיקות דם?"))

    t5 = tid()
    h.append({"role": "assistant", "content": [
        text_block(""),
        tool_use_block("validate_student_answer", {
            "question": "תינוק בן שבועיים עם חום 38.5C — מה הפרוטוקול המלא?",
            "student_answer": "בדיקות דם",
            "correct_answer": "אשפוז + sepsis workup מלא + אנטיביוטיקה IV"
        }, t5)
    ]})
    h.append(user_tool_result(t5, {
        "grade": "partial", "score": 35,
        "feedback": "בדיקות דם הן חלק מהתשובה אבל חסרים אשפוז, LP ואנטיביוטיקה IV.",
        "correct_answer": "אשפוז + sepsis workup (CBC, תרביות דם, שתן, LP) + אנטיביוטיקה IV empiric"
    }))

    # AUTO: reveal_answer (attempt 3)
    t6 = tid()
    h.append({"role": "assistant", "content": [
        text_block("[System: Student failed 3 times. Revealing answer now.]"),
        tool_use_block("reveal_answer", {
            "question": "תינוק בן שבועיים עם חום 38.5C — מה הפרוטוקול המלא?",
            "answer": "אשפוז + sepsis workup מלא (CBC, תרביות דם, תרבית שתן, LP) + אנטיביוטיקה IV empiric (Ampicillin + Gentamicin)"
        }, t6)
    ]})
    h.append(user_tool_result(t6, {
        "revealed": True,
        "answer": "אשפוז + sepsis workup מלא: CBC, CRP, תרביות דם, שתן, LP + Ampicillin + Gentamicin IV",
        "explanation": "תינוק מתחת לגיל 28 יום עם חום = full sepsis workup ואשפוז ללא יוצא מן הכלל."
    }))

    h.append(asst_text("הנה התשובה המלאה: **אשפוז + Sepsis Workup** — CBC, תרביות דם, שתן, LP + Ampicillin/Gentamicin IV. עכשיו הסבר לי: למה בדיוק צריך LP בתינוק מתחת לחודש?"))

    # Turn 4: correct answer on explanation
    h.append(user_msg("כי מנינגיטיס יכולה להיות ללא תסמינים קלאסיים בגיל הזה, מערכת החיסון לא מגיבה כמו אצל ילדים גדולים"))

    t7 = tid()
    h.append({"role": "assistant", "content": [
        text_block(""),
        tool_use_block("validate_student_answer", {
            "question": "למה צריך LP בתינוק מתחת לגיל חודש עם חום?",
            "student_answer": "מנינגיטיס יכולה להיות ללא תסמינים קלאסיים, מערכת החיסון לא בשלה",
            "correct_answer": "Meningitis ב-neonates חסרת סימנים קלאסיים — neck stiffness נדיר, ולכן LP חובה"
        }, t7)
    ]})
    h.append(user_tool_result(t7, {
        "grade": "correct", "score": 92,
        "feedback": "מצוין! בדיוק — neonatal meningitis לרוב ללא קשיון עורף. LP היא הדרך היחידה לאבחן."
    }))

    # flag_safety_critical
    t8 = tid()
    h.append({"role": "assistant", "content": [
        text_block("תשובה מעולה! אגב, נושא זה קריטי מבחינת בטיחות."),
        tool_use_block("flag_safety_critical", {
            "topic": "neonatal fever management",
            "concern": "Failure to perform LP in febrile neonate can miss bacterial meningitis with 100% mortality if untreated"
        }, t8)
    ]})
    h.append(user_tool_result(t8, {
        "flagged": True,
        "severity": "critical",
        "message": "🚨 SAFETY: פספוס מנינגיטיס בילוד עם חום = תוצאה קטלנית. LP חובה תמיד בגיל 0-28 יום.",
        "guideline": "AAP 2021: Full sepsis evaluation mandatory for all febrile neonates <28 days"
    }))

    h.append(asst_text("🚨 **נקודת בטיחות קריטית:** LP בילוד עם חום היא חובה. פספוס מנינגיטיס בגיל זה = אסון."))

    return h

# ════════════════════════════════════════════════════════════════════════════════
# SESSION 2 — compare_sources + generate_mcq + session_summary +
#              suggest_next_topic + spaced_repetition
# ════════════════════════════════════════════════════════════════════════════════

def build_session2():
    h = []

    # Turn 1: retrieve + MCQ
    h.append(user_msg("בוא נתרגל שאלות רב-ברירה על פריחות"))

    t1 = tid()
    h.append({"role": "assistant", "content": [
        text_block("נהדר! אני מביא חומר על פריחות ילדים."),
        tool_use_block("retrieve_chunks", {"query": "pediatric rashes differential diagnosis", "k": 4}, t1)
    ]})
    h.append(user_tool_result(t1, {
        "chunks_found": 4,
        "chunks": [
            {"id": "klieg_p210_c1", "source": "Kliegman", "page": 210, "score": 0.93,
             "text": "Petechial rash with fever suggests meningococcemia — emergency. Non-blanching rash requires immediate evaluation..."},
            {"id": "klieg_p215_c2", "source": "Kliegman", "page": 215, "score": 0.89,
             "text": "Kawasaki disease: fever >5 days + 4 of 5 criteria (rash, conjunctivitis, mucous membrane changes, lymphadenopathy, extremity changes)..."},
            {"id": "aap_p88_c3",   "source": "AAP Guidelines", "page": 88, "score": 0.85,
             "text": "Varicella: polymorphic lesions in different stages (macule→papule→vesicle→crust), pruritic, centripetal distribution..."},
            {"id": "klieg_p220_c4", "source": "Kliegman", "page": 220, "score": 0.81,
             "text": "Scarlet fever: sandpaper rash, strawberry tongue, Pastia lines, follows strep pharyngitis..."}
        ]
    }))

    # compare_sources
    t2 = tid()
    h.append({"role": "assistant", "content": [
        text_block("ראיתי שיש הבדלים בין Kliegman ל-AAP לגבי וריצלה. אבדוק זאת."),
        tool_use_block("compare_sources", {"topic": "varicella management", "query": "chickenpox treatment guidelines"}, t2)
    ]})
    h.append(user_tool_result(t2, {
        "topic": "varicella management",
        "comparison": [
            {"source": "Kliegman", "page": 215,
             "position": "Acyclovir recommended for immunocompromised and adolescents >12y"},
            {"source": "AAP Red Book", "page": 88,
             "position": "Acyclovir for healthy children only if started within 24h of rash AND high-risk features"}
        ],
        "consensus": "Both agree: acyclovir for high-risk patients; symptomatic care for healthy young children",
        "divergence": "AAP more conservative about routine acyclovir in healthy children"
    }))

    h.append(asst_text("מעניין — יש הבדל קל בין המקורות לגבי Acyclovir בוריצלה. Kliegman מרחיב יותר. ועכשיו שאלת MCQ:"))

    # generate_mcq
    t3 = tid()
    h.append({"role": "assistant", "content": [
        text_block(""),
        tool_use_block("generate_mcq", {
            "topic": "petechial rash in febrile child",
            "difficulty": "intermediate",
            "num_options": 4
        }, t3)
    ]})
    h.append(user_tool_result(t3, {
        "question": "ילד בן 6 עם חום 39.5°C ופריחה פטכיאלית על הגו. BP 90/60. מה הצעד הראשון?",
        "options": [
            "A. CT ראש לאחר מכן LP",
            "B. פניצילין IV מיידי לפני כל בדיקה",
            "C. תרביות דם ואז אנטיביוטיקה",
            "D. אשפוז לתצפית ללא אנטיביוטיקה"
        ],
        "correct": "B",
        "explanation": "מנינגוקוקמיה — פניצילין IV מיידי לפני LP ולפני CT. כל עיכוב מגביר תמותה.",
        "difficulty": "intermediate"
    }))

    h.append(asst_text("""**שאלת MCQ — פריחה פטכיאלית:**
ילד בן 6 עם חום 39.5°C ופריחה פטכיאלית. BP 90/60.

א. CT ראש ואז LP
ב. פניצילין IV מיידי לפני כל בדיקה
ג. תרביות דם ואז אנטיביוטיקה
ד. אשפוז לתצפית

מה תענה?"""))

    # Turn 2: correct
    h.append(user_msg("ב — פניצילין מיידי"))

    t4 = tid()
    h.append({"role": "assistant", "content": [
        text_block(""),
        tool_use_block("validate_student_answer", {
            "question": "MCQ: פריחה פטכיאלית + חום — מה הצעד הראשון?",
            "student_answer": "B — פניצילין IV מיידי",
            "correct_answer": "B — פניצילין IV מיידי לפני LP"
        }, t4)
    ]})
    h.append(user_tool_result(t4, {
        "grade": "correct", "score": 100,
        "feedback": "מושלם! מנינגוקוקמיה = חרום. פניצילין לפני הכל — גם לפני LP, גם לפני CT."
    }))

    # 3 more turns abbreviated...
    for i, (q, a, score) in enumerate([
        ("מה ה-5 קריטריונים של קוואסאקי?", "חום 5 ימים + פריחה, קונג'ונקטיביטיס, שינויי ריריות, לימפאדנופתיה, שינויי גפיים", 95),
        ("מה ההבדל בין פריחה ב-scarlet fever לוריצלה?", "ב-scarlet fever: פפולות אחידות כמו נייר זכוכית. בוריצלה: פולימורפיסם — שלבים שונים", 88),
        ("מה הטיפול בקוואסאקי?", "IVIG + Aspirin במינון גבוה", 100),
    ], start=2):
        h.append(user_msg(a))
        tv = tid()
        h.append({"role": "assistant", "content": [
            text_block(""),
            tool_use_block("validate_student_answer", {"question": q, "student_answer": a, "correct_answer": a}, tv)
        ]})
        h.append(user_tool_result(tv, {"grade": "correct", "score": score, "feedback": "כל הכבוד!"}))
        h.append(asst_text(f"ציון {score}/100 — מצוין! ממשיכים."))

    # AUTO: session_summary (after 5 questions)
    ts = tid()
    h.append({"role": "assistant", "content": [
        text_block("[System: Auto-firing session_summary after 5 questions.]"),
        tool_use_block("session_summary", {
            "weak_areas": ["Kawasaki criteria threshold"],
            "covered_topics": ["febrile petechial rash", "varicella", "scarlet fever", "Kawasaki disease"]
        }, ts)
    ]})
    h.append(user_tool_result(ts, {
        "summary": "5 שאלות הושלמו. דיוק: 96%. נושאים שנלמדו: פריחות קדחתניות, מנינגוקוקמיה, קוואסאקי, וריצלה, scarlet fever.",
        "weak_areas": ["Kawasaki criteria — pragmatic threshold vs. classic definition"],
        "mastered": ["petechial rash emergency management", "varicella recognition"]
    }))

    # AUTO: suggest_next_topic
    tnt = tid()
    h.append({"role": "assistant", "content": [
        text_block("[System: Auto-firing suggest_next_topic after summary.]"),
        tool_use_block("suggest_next_topic", {
            "weak_areas": ["Kawasaki criteria threshold"],
            "topics_covered": ["febrile petechial rash", "varicella", "scarlet fever", "Kawasaki disease"]
        }, tnt)
    ]})
    h.append(user_tool_result(tnt, {
        "next_topic": "Stevens-Johnson Syndrome vs. Kawasaki — differential diagnosis",
        "reason": "Kawasaki היה הנושא החלש ביותר; SJS מחמיר כשלא מאובחן — נושא בטיחות קריטי.",
        "difficulty": "advanced"
    }))

    # AUTO: spaced_repetition
    tsr = tid()
    h.append({"role": "assistant", "content": [
        text_block("[System: Auto-firing spaced_repetition after summary.]"),
        tool_use_block("spaced_repetition", {
            "weak_areas": ["Kawasaki criteria threshold"],
            "mastered_topics": ["petechial rash emergency management", "varicella recognition", "scarlet fever"]
        }, tsr)
    ]})
    h.append(user_tool_result(tsr, {
        "schedule": [
            {"topic": "Kawasaki disease — criteria drill", "review_in": "מחר", "priority": "high"},
            {"topic": "SJS vs Kawasaki differential", "review_in": "3 ימים", "priority": "high"},
            {"topic": "Petechial rash emergency", "review_in": "שבוע", "priority": "medium"},
            {"topic": "Scarlet fever", "review_in": "שבועיים", "priority": "low"}
        ],
        "message": "לוח חזרות אישי נוצר. שמור אותו! Kawasaki דורש חזרה מחר."
    }))

    h.append(asst_text("""📋 **סיכום Session:**
✅ 5 שאלות | דיוק 96% | 🔥 Streak 4

📅 **לוח חזרות:**
- **מחר:** Kawasaki criteria (נקודת חולשה)
- **3 ימים:** SJS vs Kawasaki differential
- **שבוע:** חזרה על פריחה פטכיאלית

הנושא הבא המומלץ: **Stevens-Johnson Syndrome**"""))

    return h


# ════════════════════════════════════════════════════════════════════════════════
# SESSION 3 — generate_clinical_case + full tool showcase
# ════════════════════════════════════════════════════════════════════════════════

def build_session3():
    h = []

    h.append(user_msg("תציג לי מקרה קליני מאתגר על נשימה"))

    t1 = tid()
    h.append({"role": "assistant", "content": [
        text_block("בשמחה! אני מייצר מקרה קליני ומביא חומר רלוונטי."),
        tool_use_block("retrieve_chunks", {"query": "pediatric respiratory distress bronchiolitis asthma", "k": 4}, t1)
    ]})
    h.append(user_tool_result(t1, {
        "chunks_found": 4,
        "chunks": [
            {"id": "klieg_p310_c1", "source": "Kliegman", "page": 310, "score": 0.94,
             "text": "Bronchiolitis: RSV most common cause in <2 years. Supportive care, O2 if SpO2<90%, hydration. Avoid bronchodilators routinely..."},
            {"id": "aap_p145_c2",  "source": "AAP Guidelines", "page": 145, "score": 0.91,
             "text": "Severe asthma: SABA q20min x3, systemic steroids, O2, consider Mg sulfate, PICU if no response..."},
            {"id": "klieg_p315_c3", "source": "Kliegman", "page": 315, "score": 0.86,
             "text": "Foreign body aspiration: sudden choking + unilateral wheeze + decreased breath sounds. CXR expiratory. Bronchoscopy."},
            {"id": "aap_p150_c4",  "source": "AAP Guidelines", "page": 150, "score": 0.82,
             "text": "Croup: barking cough, stridor, subglottic narrowing. Dexamethasone + nebulized epinephrine for moderate-severe."}
        ]
    }))

    # generate_clinical_case
    t2 = tid()
    h.append({"role": "assistant", "content": [
        text_block(""),
        tool_use_block("generate_clinical_case", {
            "topic": "respiratory distress in toddler",
            "difficulty": "advanced",
            "include_vitals": True
        }, t2)
    ]})
    h.append(user_tool_result(t2, {
        "case": """ילד בן 18 חודשים מגיע עם קוצר נשימה שהחל לפני 2 שעות, פתאומי, בזמן אכילה.
**סימנים חיוניים:** HR 148, RR 42, SpO2 88%, T 36.8°C, BP 95/60.
**בדיקה:** רתיעת גבות, stridor אינספירטורי, קולות נשימה מופחתים בצד ימין, ללא wheeze.
**היסטוריה:** בריא לפני כן, ללא חום, ללא חשיפה ל-URI.""",
        "questions": [
            "מה האבחנה הסבירה ביותר?",
            "מה הצעד הדחוף ביותר?",
            "אילו בדיקות תבקש?"
        ],
        "diagnosis": "Foreign body aspiration",
        "difficulty": "advanced"
    }))

    h.append(asst_text("""🏥 **מקרה קליני — ד"ר, ייעוץ דחוף:**

ילד בן 18 חודשים — קוצר נשימה **פתאומי** בזמן אכילה.
SpO2 88% | RR 42 | HR 148 | ללא חום

בדיקה: **Stridor אינספירטורי**, קולות מופחתים בצד ימין, ללא wheeze.

מה האבחנה הסבירה ביותר ומה הצעד הדחוף?"""))

    # Student correct
    h.append(user_msg("Foreign body aspiration — לקחת CXR עם פלט ולשקול ברונכוסקופיה"))

    t3 = tid()
    h.append({"role": "assistant", "content": [
        text_block(""),
        tool_use_block("validate_student_answer", {
            "question": "מה האבחנה ומה הצעד הדחוף בילד 18 חודשים עם stridor פתאומי + קולות מופחתים בצד ימין?",
            "student_answer": "Foreign body aspiration — CXR + ברונכוסקופיה",
            "correct_answer": "Foreign body aspiration — O2, CXR expiratory, rigid bronchoscopy"
        }, t3)
    ]})
    h.append(user_tool_result(t3, {
        "grade": "correct", "score": 90,
        "feedback": "מעולה! Foreign body aspiration. CXR בנשיפה — לחפש air trapping או mediastinal shift. ברונכוסקופיה היא הטיפול."
    }))

    # compare_sources on bronchiolitis vs asthma
    t4 = tid()
    h.append({"role": "assistant", "content": [
        text_block("שאלה נוספת: מה ההבדל בין ברונכיוליטיס לאסטמה בגיל הזה? אבדוק מה המקורות אומרים."),
        tool_use_block("compare_sources", {"topic": "bronchiolitis vs asthma in toddlers", "query": "bronchiolitis asthma differential toddler"}, t4)
    ]})
    h.append(user_tool_result(t4, {
        "topic": "bronchiolitis vs asthma differential",
        "comparison": [
            {"source": "Kliegman", "page": 310, "position": "Bronchiolitis: first episode wheeze <2y, viral trigger, no response to bronchodilators"},
            {"source": "AAP Guidelines", "page": 145, "position": "Recurrent wheeze in toddler = probable asthma; trial of bronchodilator diagnostic"}
        ],
        "consensus": "First episode <2y with RSV = bronchiolitis. Recurrent episodes = likely asthma.",
        "divergence": "Threshold for bronchodilator trial differs: Kliegman more conservative"
    }))

    h.append(asst_text("""**השוואת מקורות — Bronchiolitis vs Asthma:**

| | Kliegman | AAP |
|---|---|---|
| First wheeze <2y | Bronchiolitis | Bronchiolitis |
| Bronchodilator | לא כברירת מחדל | Trial אבחנתי |
| Recurrent wheeze | שקול אסטמה | Probable asthma |

ממשיכים עם שאלה על Croup."""))

    return h


# ════════════════════════════════════════════════════════════════════════════════
# Build all sessions
# ════════════════════════════════════════════════════════════════════════════════

sessions = [
    {
        "sid": "demo0001",
        "label": "חום בילוד — כל הכלים (retrieve, validate, hint, reveal, flag_safety, check_prereq)",
        "history": build_session1(),
        "questions_asked":  4,
        "correct_answers":  2,
        "topics_covered":   ["neonatal fever", "sepsis workup", "neonatal meningitis", "LP indication"],
        "weak_areas":       ["sepsis workup protocol steps"],
        "attempt_count":    0,
        "streak":           1,
        "tool_usage":       {"retrieve_chunks": 1, "check_prerequisites": 1, "validate_student_answer": 3,
                             "give_hint": 1, "reveal_answer": 1, "flag_safety_critical": 1},
        "difficulty_level": "intermediate",
        "created_at":       NOW - 3 * DAY,
    },
    {
        "sid": "demo0002",
        "label": "פריחות — MCQ + compare_sources + session_summary + suggest_next_topic + spaced_repetition",
        "history": build_session2(),
        "questions_asked":  5,
        "correct_answers":  5,
        "topics_covered":   ["petechial rash", "meningococcemia", "varicella", "scarlet fever", "Kawasaki disease"],
        "weak_areas":       ["Kawasaki criteria threshold"],
        "attempt_count":    0,
        "streak":           4,
        "tool_usage":       {"retrieve_chunks": 1, "compare_sources": 1, "generate_mcq": 1,
                             "validate_student_answer": 5, "session_summary": 1,
                             "suggest_next_topic": 1, "spaced_repetition": 1},
        "difficulty_level": "advanced",
        "created_at":       NOW - 1 * DAY,
    },
    {
        "sid": "demo0003",
        "label": "נשימה — generate_clinical_case + compare_sources + foreign body aspiration",
        "history": build_session3(),
        "questions_asked":  3,
        "correct_answers":  3,
        "topics_covered":   ["foreign body aspiration", "bronchiolitis", "asthma toddler", "croup"],
        "weak_areas":       [],
        "attempt_count":    0,
        "streak":           3,
        "tool_usage":       {"retrieve_chunks": 1, "generate_clinical_case": 1,
                             "validate_student_answer": 1, "compare_sources": 1},
        "difficulty_level": "advanced",
        "created_at":       NOW - 2 * DAY,
    },
]

TOOLS_SHOWN = set()
for s in sessions:
    TOOLS_SHOWN.update(s["tool_usage"].keys())

for s in sessions:
    data = {
        "history":              s["history"],
        "questions_asked":      s["questions_asked"],
        "correct_answers":      s["correct_answers"],
        "topics_covered":       s["topics_covered"],
        "weak_areas":           s["weak_areas"],
        "attempt_count":        s["attempt_count"],
        "streak":               s["streak"],
        "current_chunks":       [],
        "last_question":        "",
        "last_correct_ans":     "",
        "tool_usage":           s["tool_usage"],
        "last_summary_at":      5 if "session_summary" in s["tool_usage"] else 0,
        "last_tool":            list(s["tool_usage"].keys())[-1],
        "last_score":           None,
        "difficulty_level":     s["difficulty_level"],
        "prerequisites_checked": [],
        "created_at":           s["created_at"],
    }
    path = SESSIONS_DIR / f"{s['sid']}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    n, c = s["questions_asked"], s["correct_answers"]
    print(f"OK {s['sid']}  q={n}  acc={round(c/n*100)}%  tools={list(s['tool_usage'].keys())}")

all_tools = {
    "retrieve_chunks", "validate_student_answer", "compare_sources", "give_hint",
    "reveal_answer", "generate_clinical_case", "suggest_next_topic", "session_summary",
    "generate_mcq", "flag_safety_critical", "check_prerequisites", "spaced_repetition"
}
missing = all_tools - TOOLS_SHOWN
print(f"\nTools shown: {sorted(TOOLS_SHOWN)}")
if missing:
    print(f"MISSING tools: {missing}")
else:
    print("All 12 tools covered!")
print(f"Saved {len(sessions)} sessions to {SESSIONS_DIR}")
