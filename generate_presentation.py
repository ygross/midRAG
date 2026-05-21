# -*- coding: utf-8 -*-
"""
generate_presentation.py — מדריך הצגה בעברית: כיצד להסביר את פרויקט ה-RAG למרצה.
"""

from bidi.algorithm import get_display as _bidi

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

pdfmetrics.registerFont(TTFont("Arial",       "C:/Windows/Fonts/arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold",  "C:/Windows/Fonts/arialbd.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Italic","C:/Windows/Fonts/ariali.ttf"))

OUTPUT = "presentation_guide.pdf"

def H(t): return _bidi(t)

# ── Colours ───────────────────────────────────────────────────────────────────
NAVY      = HexColor("#1a3a5c")
BLUE      = HexColor("#2e6da4")
BLUE_LT   = HexColor("#d6e8f7")
TEAL      = HexColor("#0e7c7b")
TEAL_LT   = HexColor("#d0f0ef")
AMBER     = HexColor("#f4a400")
AMBER_LT  = HexColor("#fff3cd")
GREEN     = HexColor("#1e7e34")
GREEN_LT  = HexColor("#d4edda")
RED       = HexColor("#c0392b")
RED_LT    = HexColor("#fde8e7")
GREY_LT   = HexColor("#f5f5f5")
GREY_MID  = HexColor("#cccccc")
ORANGE    = HexColor("#e07b39")

# ── Styles ────────────────────────────────────────────────────────────────────
def make_styles():
    base = getSampleStyleSheet()

    def ps(name, **kw):
        defaults = dict(fontName="Arial", alignment=TA_RIGHT, leading=14, fontSize=9)
        defaults.update(kw)
        return ParagraphStyle(name, parent=base["Normal"], **defaults)

    title_s = ps("Title", fontSize=24, fontName="Arial-Bold", textColor=white,
                  alignment=TA_CENTER, spaceAfter=0, leading=30)
    sub_s   = ps("Sub", fontSize=13, textColor=BLUE_LT,
                  alignment=TA_CENTER, leading=18)
    h1      = ps("H1", fontSize=15, fontName="Arial-Bold", textColor=NAVY,
                  spaceBefore=14, spaceAfter=5, leading=20)
    h2      = ps("H2", fontSize=12, fontName="Arial-Bold", textColor=BLUE,
                  spaceBefore=10, spaceAfter=4, leading=16)
    h3      = ps("H3", fontSize=10, fontName="Arial-Bold", textColor=NAVY,
                  spaceBefore=7, spaceAfter=3, leading=14)
    body    = ps("Body", fontSize=9, leading=14, spaceAfter=3)
    bul     = ps("Bul",  fontSize=9, leading=14, rightIndent=14, spaceAfter=2)
    note    = ps("Note", fontSize=8, fontName="Arial-Italic",
                  textColor=HexColor("#555555"))
    say     = ps("Say",  fontSize=9, fontName="Arial-Italic", textColor=NAVY,
                  leading=14, spaceAfter=2)
    code    = ParagraphStyle("Code", parent=base["Normal"], fontName="Courier",
                               fontSize=7.5, leading=11, leftIndent=8,
                               backColor=GREY_LT, borderPadding=4, alignment=TA_LEFT)
    tip_txt = ps("Tip",  fontSize=9, textColor=HexColor("#1a3a2a"), leading=13)
    warn_txt= ps("Warn", fontSize=9, textColor=HexColor("#5a2000"), leading=13)
    num_lbl = ps("Num",  fontSize=20, fontName="Arial-Bold", textColor=white,
                  alignment=TA_CENTER, leading=24)
    step_hdr= ps("StepH", fontSize=11, fontName="Arial-Bold", textColor=NAVY,
                  leading=15)
    qa_q    = ps("QQ", fontSize=9, fontName="Arial-Bold", textColor=RED,
                  spaceBefore=6, spaceAfter=2)
    qa_a    = ps("QA", fontSize=9, textColor=HexColor("#1a3a5c"),
                  rightIndent=10, leading=14)
    time_s  = ps("Time", fontSize=9, fontName="Arial-Bold", textColor=TEAL,
                  alignment=TA_CENTER)

    return dict(title=title_s, sub=sub_s, h1=h1, h2=h2, h3=h3, body=body,
                bul=bul, note=note, say=say, code=code, tip=tip_txt,
                warn=warn_txt, num=num_lbl, step=step_hdr, qq=qa_q, qa=qa_a,
                time=time_s)


def SP(h=0.25): return Spacer(1, h * cm)
def HR(c=GREY_MID): return HRFlowable(width="100%", thickness=0.5, color=c)


# ── Building blocks ───────────────────────────────────────────────────────────

def colored_box(content_rows, bg, border=None, padding=8):
    """Wrap a list of Paragraph objects in a colored box."""
    data = [[item] for item in content_rows]
    t = Table(data, colWidths=[16.5 * cm])
    style = [
        ("BACKGROUND",    (0, 0), (-1, -1), bg),
        ("TOPPADDING",    (0, 0), (-1, -1), padding),
        ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
        ("LEFTPADDING",   (0, 0), (-1, -1), padding + 2),
        ("RIGHTPADDING",  (0, 0), (-1, -1), padding + 2),
    ]
    if border:
        style += [("BOX", (0, 0), (-1, -1), 1.2, border),
                  ("LINEAFTER", (0, 0), (0, -1), 4, border)]
    t.setStyle(TableStyle(style))
    return t


def say_box(text, S):
    """Blue 'say this' speech box."""
    return colored_box(
        [Paragraph(H("💬  " + text), S["say"])],
        bg=BLUE_LT, border=BLUE, padding=7
    )


def tip_box(title_he, text, S):
    """Green tip box."""
    return colored_box(
        [Paragraph(H("✔  " + title_he), S["h3"]),
         Paragraph(H(text), S["tip"])],
        bg=GREEN_LT, border=GREEN, padding=7
    )


def warn_box(title_he, text, S):
    """Amber warning box."""
    return colored_box(
        [Paragraph(H("⚠  " + title_he), S["h3"]),
         Paragraph(H(text), S["warn"])],
        bg=AMBER_LT, border=AMBER, padding=7
    )


def step_header(num, title_he, duration_he, S):
    """Numbered step header with duration badge."""
    num_cell  = Table([[Paragraph(str(num), S["num"])]], colWidths=[1.0 * cm],
                       rowHeights=[1.0 * cm])
    num_cell.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))

    dur_cell  = Table([[Paragraph(H(duration_he), S["time"])]], colWidths=[2.5 * cm],
                       rowHeights=[1.0 * cm])
    dur_cell.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), TEAL),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))

    title_cell = Table([[Paragraph(H(title_he), S["step"])]], colWidths=[12.8 * cm],
                        rowHeights=[1.0 * cm])
    title_cell.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BLUE_LT),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))

    outer = Table([[num_cell, title_cell, dur_cell]],
                   colWidths=[1.0 * cm, 12.8 * cm, 2.7 * cm],
                   rowHeights=[1.0 * cm])
    outer.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return outer


def qa_pair(q, a, S):
    return [
        Paragraph(H("ש:  " + q), S["qq"]),
        Paragraph(H(a), S["qa"]),
        SP(0.08),
    ]


def bullet(text, S):
    return Paragraph(H("•  " + text), S["bul"])


def make_table(data, col_widths, header_bg=BLUE):
    style = [
        ("BACKGROUND",    (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR",     (0, 0), (-1, 0), white),
        ("FONTNAME",      (0, 0), (-1, 0), "Arial-Bold"),
        ("FONTNAME",      (0, 1), (-1, -1), "Arial"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("ROWBACKGROUND", (0, 1), (-1, -1), [white, GREY_LT]),
        ("GRID",          (0, 0), (-1, -1), 0.4, GREY_MID),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("ALIGN",         (0, 0), (-1, -1), "RIGHT"),
    ]
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle(style))
    return t


# ── Cover ─────────────────────────────────────────────────────────────────────
def cover(S):
    cover_data = [[Paragraph(H("מדריך הצגת הפרויקט למרצה"), S["title"])]]
    ct = Table(cover_data, colWidths=[17 * cm])
    ct.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
        ("TOPPADDING",    (0, 0), (-1, -1), 32),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 32),
    ]))
    return [
        ct,
        SP(0.3),
        Paragraph(H("פרויקט RAG רפואת ילדים — בנייה, קוד, הבנה"), S["sub"]),
        SP(0.15),
        Paragraph(H("מה להגיד · איך לסביר · מה להדגים · שאלות צפויות"), S["sub"]),
        SP(0.5),
        HRFlowable(width="100%", thickness=1.5, color=BLUE),
        SP(0.3),
    ]


# ── Content ───────────────────────────────────────────────────────────────────
def build_content(S):
    story = []
    story += cover(S)

    # ── מבנה ההצגה ────────────────────────────────────────────────────────────
    story += [
        Paragraph(H("מבנה ההצגה המומלץ — 20 דקות"), S["h1"]),
        SP(0.1),
    ]

    timeline_data = [
        [H("שלב"), H("נושא"), H("זמן"), H("מטרה")],
        ["1", H("פתיחה + הבעיה"), H("2 דק'"),  H("לתפוס עניין — 'למה בכלל RAG?'")],
        ["2", H("ארכיטקטורה ויזואלית"), H("3 דק'"), H("תמונה שלמה לפני פרטים")],
        ["3", H("הסבר הקוד — build_index"), H("4 דק'"), H("הדגמת הבנה טכנית")],
        ["4", H("הסבר הקוד — retrieval + generation"), H("3 דק'"), H("זרימה מקצה לקצה")],
        ["5", H("תוצאות הערכה + ablation"), H("4 דק'"), H("מספרים אמיתיים + ניתוח")],
        ["6", H("לקחים ושיפורים"), H("2 דק'"), H("עומק הבנה — חשיבה ביקורתית")],
        ["7", H("שאלות"), H("2 דק'"), H("גמישות מחשבתית")],
    ]
    story += [
        make_table(timeline_data, [1.0*cm, 5.5*cm, 1.8*cm, 8.2*cm]),
        SP(),
    ]

    story += [
        tip_box("עצה כללית",
                "פתח תמיד עם 'למה' לפני 'מה'. המרצה רוצה לראות שהבנת את הבעיה "
                "שהטכנולוגיה באה לפתור, לא רק שכתבת קוד שעובד.", S),
        SP(0.3),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 1
    # ══════════════════════════════════════════════════════════════════════════
    story += [step_header(1, "פתיחה — הבעיה שפותרים", "2 דקות", S), SP(0.15)]

    story += [
        Paragraph(H("מה לפתוח איתו:"), S["h3"]),
        say_box(
            "הפרויקט שלי בונה מערכת RAG — Retrieval-Augmented Generation — "
            "שמאפשרת לשאול שאלות קליניות על ספרי לימוד ברפואת ילדים ולקבל תשובות "
            "מושרשות במקור, עם ציטוט מדויק לעמוד.", S),
        SP(0.15),
        Paragraph(H("אז תסביר מיד: למה לא מספיק GPT/Claude רגיל?"), S["h3"]),
        say_box(
            "מודל שפה כללי לא יודע את המקרים הספציפיים בספר AAP 2022 — "
            "שמעון, ילד עם פרכוס חומי, אמה עם נשימה מהירה. "
            "הוא ייתן תשובה שנשמעת נכון אבל ממציאה פרטים. "
            "RAG מאלץ כל תשובה לבוא ישירות מהטקסט שאוחזר — "
            "שורה ממש מהספר — ומצטט את העמוד המדויק.", S),
        SP(0.15),
        tip_box("נקודת זמן חשובה",
                "תגיד את המשפט הזה: 'הבדיקה הפשוטה היא לשאול את אותה שאלה "
                "ל-Claude ללא RAG — הוא מהזה תשובה שנשמעת רפואית אבל לא מופיעה "
                "בשום ספר.'  זה מוכיח שהבנת מתי RAG נחוץ.", S),
        SP(),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 2
    # ══════════════════════════════════════════════════════════════════════════
    story += [step_header(2, "ארכיטקטורה — תמונה שלמה", "3 דקות", S), SP(0.15)]

    story += [
        Paragraph(H("הצג את תרשים הארכיטקטורה ועבור על כל שלב בשורה:"), S["h3"]),
        SP(0.08),
    ]

    arch_rows = [
        (H("קבצי PDF"), H("שני ספרים — 1,096 עמודים לאחר דילוג עמודי תמונה (פחות מ-50 תווים).")),
        (H("טעינה + ניקוי"), H("PyMuPDF חולץ טקסט עמוד-עמוד. clean_text() מסיר עיוותי PDF: מספרי עמודים, שלוש שורות ריקות, bullet בודד.")),
        (H("פיצול לחלקים"), H("שתי אסטרטגיות במקביל: גודל-קבוע (400 תווים, חפיפה 50) ופסקה (100–700 תווים לפי גבול טבעי). סה\"כ 10,107 + 5,250 chunks.")),
        (H("הטמעה"), H("all-MiniLM-L6-v2 — מודל 384-ממד, מנורמל L2. 227 שניות על CPU ל-10K chunks. הנרמול הופך קוסינוס למכפלת נקודות.")),
        (H("אינדקס numpy"), H("קבצי .npy + .json. אין מסד נתונים חיצוני. במקור ChromaDB — הוחלף בגלל תקלת Windows שמנעה persistence בין תהליכים.")),
        (H("חיפוש + יצירה"), H("scores = embeddings @ qvec.T → np.argpartition → top-5 chunks → פרומפט ל-Claude haiku → תשובה + ציטוט [Source: ...].")),
    ]
    for label, desc in arch_rows:
        row = Table([[Paragraph(label, S["h3"]), Paragraph(desc, S["body"])]],
                     colWidths=[3.5*cm, 13*cm])
        row.setStyle(TableStyle([
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (0,0), (-1,-1), 0),
            ("RIGHTPADDING",  (0,0), (-1,-1), 0),
            ("LINEBELOW",     (0,0), (-1,-1), 0.3, GREY_MID),
        ]))
        story += [row]

    story += [
        SP(0.2),
        warn_box("טעות נפוצה",
                 "אל תגיד 'השתמשתי ב-ChromaDB'. השתמשת ב-ChromaDB אבל גילית "
                 "תקלת Windows ועברת ל-numpy. זה בדיוק מה שמרצה רוצה לשמוע — "
                 "שנתקלת בבעיה אמיתית וחשבת על פתרון.", S),
        SP(),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 3
    # ══════════════════════════════════════════════════════════════════════════
    story += [step_header(3, "הסבר הקוד — build_index.py", "4 דקות", S), SP(0.15)]

    story += [
        Paragraph(H("פתח את הקובץ src/build_index.py ועבור על 4 הפונקציות הראשיות:"), S["h3"]),
        SP(0.1),
    ]

    code_explain = [
        ("load_all_documents()", H("פונקציה ב-utils.py. PyMuPDF פותח כל PDF, מחלץ טקסט עמוד-עמוד, מריץ clean_text(), בונה section_map מהTOC. מחזיר רשימת {doc_id, text, metadata}.")),
        ("chunk_fixed_size(docs, size=400, overlap=50)", H("חלון נגרר. step = size - overlap = 350. כל שלב מוסיף chunk[text[i : i+400]]. tail < 30 תווים — נזרק.")),
        ("embed_chunks(model, chunks, batch=128)", H("model.encode(texts, normalize_embeddings=True). normalize=True → L2 norm → cosine == dot product. מחזיר float32 array (N, 384).")),
        ("save_index(chunks, embeddings, name)", H("np.save(f'{name}_embeddings.npy', embeddings) + json.dump chunks לקובץ. קריאה עם np.load — 0 תלויות חיצוניות.")),
    ]

    for func, desc in code_explain:
        story += [
            Paragraph(func, S["code"]),
            Paragraph(H(desc), S["body"]),
            SP(0.1),
        ]

    story += [
        say_box(
            "כשאתה מראה את embed_chunks, תגיד: "
            "'שים לב ל-normalize_embeddings=True — זה הסיבה שאפשר לחשב קוסינוס "
            "פשוט עם @ ולא צריך לחלק בגודל הוקטורים. "
            "זה גם מה שמאפשר לאחסן ב-.npy פשוט במקום מסד נתונים מיוחד.'", S),
        SP(0.15),
        Paragraph(H("הקוד שכדאי להכיר בעל פה:"), S["h3"]),
        Paragraph(
            "vectors = model.encode(texts, batch_size=128, normalize_embeddings=True)\n"
            "np.save('fixed_embeddings.npy', vectors.astype(np.float32))",
            S["code"]),
        SP(),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 4
    # ══════════════════════════════════════════════════════════════════════════
    story += [step_header(4, "הסבר הקוד — retrieval.py + rag_system.py", "3 דקות", S), SP(0.15)]

    story += [
        Paragraph(H("פתח src/retrieval.py — הראה את פונקציית retrieve():"), S["h3"]),
        Paragraph(
            "qvec  = model.encode([query], normalize_embeddings=True).astype(np.float32)\n"
            "scores = (embeddings @ qvec.T).flatten()          # (N,) cosine similarity\n"
            "top_idx = np.argpartition(scores, -k)[-k:]        # O(N), no full sort\n"
            "top_idx = top_idx[np.argsort(scores[top_idx])[::-1]]",
            S["code"]),
        SP(0.1),
        say_box(
            "הקוד הזה עושה חיפוש קוסינוס על 10,107 וקטורים תוך פחות ממאית שנייה. "
            "np.argpartition הוא O(N) — לא ממיין את הכל, רק מוצא את ה-k הגדולים. "
            "אחרי שמצאתי את ה-top-k, אני ממיין רק אותם — זה הרבה יותר מהיר "
            "מ-argsort על כל המערך.", S),
        SP(0.15),
        Paragraph(H("פתח src/rag_system.py — הראה את answer():"), S["h3"]),
        Paragraph(
            "chunks  = retrieve(query, k=5, strategy='fixed')\n"
            "context = '\\n'.join(c['text'] for c in chunks)\n"
            "prompt  = f'Context:\\n{context}\\n\\nQuestion: {query}'\n"
            "response = client.messages.create(model='claude-haiku-4-5-20251001',\n"
            "                                   max_tokens=512, messages=[...])",
            S["code"]),
        SP(0.1),
        say_box(
            "שים לב שה-context בנוי מ-chunks ממוינים לפי ניקוד יורד — "
            "הרלוונטי ביותר ראשון. max_tokens=512 מספיק לתשובה קלינית עם ציטוטים "
            "ומונע יצירת פסקאות ארוכות שגולשות מה-context.", S),
        SP(),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 5
    # ══════════════════════════════════════════════════════════════════════════
    story += [step_header(5, "תוצאות ההערכה וה-Ablation", "4 דקות", S), SP(0.15)]

    story += [
        Paragraph(H("תציג את הטבלאות מהדוח ותסביר כל מספר:"), S["h3"]),
        SP(0.08),
    ]

    results_data = [
        [H("מדד"), H("ערך"), H("איך להסביר בפה")],
        ["Hit@5 = 0.827",
         H("43/52 שאלות"),
         H("'בכמעט 83% מהשאלות, הטקסט שמכיל את התשובה מופיע בחמשת ה-chunks הראשונים שהמערכת מחזירה.'")],
        ["Precision@5 = 0.881",
         H("4.4 מתוך 5"),
         H("'כמעט כל chunk שאוחזר רלוונטי — מעט רעש. זה גבוה מהצפוי בגלל שהקורפוס ממוקד.'")],
        ["Latency = 3.14s",
         H("CPU בלבד"),
         H("'הזמן מחולק: ~0.1s אחזור numpy, ~3s יצירה ב-Claude API. צוואר הבקבוק הוא ה-LLM, לא האחזור.'")],
        [H("שלילה = 1.000"),
         H("8/8 מושלם"),
         H("'הפתעה — ציפינו לזה להיות הכי קשה. כללי הפרומפט עבדו טוב לאישור היעדר.'")],
        [H("עובדתי = 0.792"),
         H("19/24 — הכי חלש"),
         H("'5 כשלים — רובם מונחי עץ-ההחלטה של קלייגמן שפיצול גודל-קבוע חתך במקום לא נכון.'")],
    ]
    story += [
        make_table(results_data, [3.5*cm, 2.5*cm, 10*cm]),
        SP(0.2),
        Paragraph(H("Ablation — זה המקום להראות הבנה עמוקה:"), S["h3"]),
        SP(0.08),
    ]

    abl_data = [
        [H("ניסוי"), H("Hit@k"), H("Precision@k"), H("מה זה אומר — תגיד בקול")],
        [H("fixed k=5 (בסיס)"), "0.900", "0.810",
         H("'הבסיס לעשרים השאלות הראשונות.'")],
        [H("para k=5"), "0.900", "0.870",
         H("'אותו Hit — אבל Precision גבוה ב-6%. פסקה מייצרת chunks יותר נכוחים.'")],
        [H("fixed k=3"), "0.850", "0.850",
         H("'Precision עולה כי פחות רעש — אבל מפסידים hit אחד מספרי.'")],
        [H("fixed k=8"), "0.900", "0.787",
         H("'Hit לא משתפר — רק מוסיפים רעש. k=5 הוא נקודת האיזון.'")],
    ]
    story += [
        make_table(abl_data, [3.5*cm, 1.8*cm, 2.5*cm, 8.7*cm]),
        SP(0.2),
        say_box(
            "תסביר את ה-ablation כך: 'הרצתי 4 ניסויים כדי להבין מה באמת משפיע. "
            "המסקנה המפתיעה: אסטרטגיית הפיצול חשובה יותר מ-k. "
            "פסקה נותנת 6% יותר precision בלי שום עלות בזמן תגובה. "
            "k=8 לא עוזר כי הוא מוסיף chunks שגויים שמבלבלים את המודל.'", S),
        SP(),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 6
    # ══════════════════════════════════════════════════════════════════════════
    story += [step_header(6, "לקחים — מה הייתי משפר", "2 דקות", S), SP(0.15)]

    story += [
        Paragraph(H("זה השלב שמפריד בין 'השתמשתי בספרייה' לבין 'הבנתי את החומר':"), S["body"]),
        SP(0.1),
    ]

    improvements = [
        (H("Cross-encoder לדירוג מחדש"),
         H("Bi-encoder מהיר אבל פחות מדויק — הוא מקודד שאילתה ו-chunk בנפרד. "
           "Cross-encoder רואה את שניהם יחד ומדויק הרבה יותר. "
           "הייתי מוסיף ms-marco-MiniLM לדירוג top-10 — עלות ~0.5 שניות, "
           "משתלם לשאלות זמניות ו-multi-hop.")),
        (H("חפיפה ברמת משפט"),
         H("עכשיו החפיפה היא 50 תווים — קטע משפט שרירותי. "
           "הייתי מחשב גבולות משפט קודם ומבטיח שכל chunk מתחיל ומסתיים במשפט שלם. "
           "זה ישפר קטגוריית 'מספרי' שבה ספרות נחתכות.")),
        (H("LLM כשופט (LLM-as-Judge)"),
         H("הערכה ידנית על 10 שאלות לא מספיקה. "
           "הייתי משתמש ב-Claude Sonnet כדי לבדוק אם התשובה שנוצרה "
           "מוסמכת על-ידי הטקסט המצוטט — "
           "מה שנקרא faithfulness check. זה מאפשר הערכה אוטומטית על כל 52 השאלות.")),
    ]

    for title, desc in improvements:
        row = Table([[Paragraph(title, S["h3"]), Paragraph(desc, S["body"])]],
                     colWidths=[4*cm, 12.5*cm])
        row.setStyle(TableStyle([
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING",   (0,0), (-1,-1), 0),
            ("RIGHTPADDING",  (0,0), (-1,-1), 0),
            ("LINEBELOW",     (0,0), (-1,-1), 0.3, GREY_MID),
        ]))
        story.append(row)

    story += [SP(0.2),
              tip_box("המשפט שסוגר את ההצגה",
                      "תסיים עם: 'הלקח הכי חשוב שלמדתי הוא שהצינור הטכני פשוט יחסית — "
                      "האתגר האמיתי הוא לאבחן איפה הכשלים ולהחליט מה לשפר קודם. "
                      "ניתוח ה-ablation הוא הכלי לזה.'", S),
              SP()]

    # ══════════════════════════════════════════════════════════════════════════
    # שאלות צפויות
    # ══════════════════════════════════════════════════════════════════════════
    story += [PageBreak()]
    story += [
        Paragraph(H("שאלות צפויות מהמרצה — ותשובות"), S["h1"]),
        SP(0.1),
        Paragraph(H("קרא את זה כמה פעמים לפני ההצגה — אלה השאלות שמפרידות בין ציון 90 ל-100."), S["note"]),
        SP(0.2),
    ]

    # Category: Conceptual
    story += [Paragraph(H("הבנה קונצפטואלית"), S["h2"]), HR(BLUE), SP(0.1)]
    for q, a in [
        ("מה ההבדל בין RAG ל-fine-tuning?",
         "Fine-tuning שוכח — הוא 'צובע' את המשקולות של המודל בנתונים חדשים "
         "אבל עלול להשכיח ידע קיים (catastrophic forgetting). "
         "RAG לא נוגע במשקולות — הוא מוסיף הקשר חיצוני בזמן ריצה. "
         "RAG גם עדכני יותר: אפשר לשנות את המסמכים בלי לאמן מחדש. "
         "Fine-tuning טוב לסגנון ולמשימות קבועות; RAG טוב לידע עובדתי שמשתנה."),
        ("למה bi-encoder ולא cross-encoder לאחזור?",
         "Cross-encoder מדויק יותר אבל O(N) — הוא צריך מעבר קדימה לכל זוג (שאילתה, document). "
         "לאינדקס של 10K chunks זה 10,000 קריאות לכל שאלה — כ-30 שניות על CPU. "
         "Bi-encoder מחשב את הטמעת השאילתה פעם אחת (384-dim) ואז מכפיל מטריצה — "
         "O(1) בהינתן אינדקס מוכן. לכן: bi-encoder לaחזור, cross-encoder ל-reranking אם נדרש."),
        ("מדוע L2 normalisation?",
         "ללא נרמול, מכפלת נקודות תלויה בגודל הוקטור — משפטים ארוכים יקבלו ניקוד גבוה יותר "
         "רק בגלל שיש בהם יותר מילים. נרמול הופך את המדד לזווית בלבד (כיוון סמנטי) "
         "ומאפשר השוואה הוגנת בין שבר של שתי מילים מעץ-ההחלטה לפסקה ארוכה."),
        ("מה זה Hit@k לעומת Precision@k?",
         "Hit@k: בינארי לשאלה — 1 אם לפחות chunk אחד נכון ב-top-k, 0 אחרת. "
         "Precision@k: ממוצע — כמה מה-k שאוחזרו רלוונטיים? "
         "Hit@k מודד recall (האם מצאנו?). Precision@k מודד דיוק (כמה רעש יש?). "
         "המטרה היא למקסם Hit תוך שמירה על Precision גבוה — k=5 הוא נקודת האיזון."),
    ]:
        story += qa_pair(q, a, S)

    story += [SP(0.1), Paragraph(H("תהליך ה-RAG"), S["h2"]), HR(BLUE), SP(0.1)]
    for q, a in [
        ("מה קורה אם ה-chunk הנכון לא אוחזר?",
         "המערכת תענה על סמך מה שאוחזר. "
         "אם אף chunk רלוונטי לא נמצא, הפרומפט מורה ל-Claude להגיד "
         "'המידע לא נמצא במקורות'. כשל ידוע: לעיתים המודל עדיין מצטט "
         "את ה-chunk הכי קרוב כ-fallback שגוי — זה failure mode שצוין בניתוח הכשלים."),
        ("למה chunk size 400 ולא 200 או 800?",
         "200: קטן מדי — fragment של משפט אחד. ההטמעה מקבלת הקשר דל ורעש גדל. "
         "800: גדול מדי — שני נושאים קליניים מתחברים לchunk אחד, האות הסמנטי מדולל. "
         "400 ≈ 80 טוקנים — כ-2 משפטים, הקשר שלם, ניקוד ייחודי. "
         "זה אומת בניסוי ablation: k שונה לא שינה הרבה, אבל אסטרטגיית הפיצול כן."),
        ("מה ההבדל בין dense retrieval ל-BM25?",
         "BM25 מחפש לפי מילות מפתח (TF-IDF variant) — אם הממביל לא מופיע בטקסט, "
         "ה-chunk לא יוחזר. Dense retrieval מחפש לפי משמעות — "
         "'febrile seizure discharge' יוחזר גם עמוד שכותב 'criteria for afebrile child'. "
         "Dense טוב לשפה טבעית; BM25 טוב לשמות מדעיים ייחודיים (שמות תרופות)."),
    ]:
        story += qa_pair(q, a, S)

    story += [SP(0.1), Paragraph(H("שאלות טכניות"), S["h2"]), HR(BLUE), SP(0.1)]
    for q, a in [
        ("למה החלפת ChromaDB ב-numpy?",
         "ChromaDB 1.5.9 יש תקלת HNSW ספציפית ל-Windows: אינדקס ה-Rust נטען בזיכרון "
         "בתהליך הבנייה אבל לא נכתב לדיסק כראוי. כל תהליך Python חדש שפתח את אותו path "
         "קיבל InternalError. ניסיתי workaround עם sleep+verify — עבד בתהליך אחד אבל לא בין תהליכים. "
         "numpy מספיק ל-10K vectors, portable לחלוטין, ו-0 תלויות נוספות."),
        ("np.argpartition לעומת np.argsort — מה ההבדל?",
         "np.argsort ממיין את כל N=10,107 האלמנטים — O(N log N). "
         "np.argpartition מוצא את k הגדולים ב-O(N) ללא מיון מלא. "
         "לאחר מכן אני ממיין רק את ה-k=5 שנמצאו — O(k log k) קבוע. "
         "בממשות: לא הבדל גדול ל-10K elements, אבל זה פתרון נכון conceptually."),
        ("למה הטמעת השאילתה ב-retrieve() ולא ב-rag_system.py?",
         "Separation of concerns: retrieval.py אחראי לכל מה שנוגע לאינדקס. "
         "rag_system.py הוא orchestrator בלבד — הוא לא יודע כלום על vektors. "
         "זה גם מאפשר לבדוק retrieval() בנפרד בלי LLM."),
        ("מה זה semantic drift?",
         "כשה-chunks ארוכים מדי, תשומת הלב של המודל 'מתפשטת' על הטקסט כולו "
         "ועשויה לענות על שאלה קרובה אבל לא זהה. "
         "דוגמה: שאלה על אוטיטיס מדיה מקבלת תשובה על דלקת אוזן כרונית "
         "כי שניהם מופיעים באותו chunk גדול."),
    ]:
        story += qa_pair(q, a, S)

    story += [SP(0.1), Paragraph(H("שאלות 'מה אם'"), S["h2"]), HR(BLUE), SP(0.1)]
    for q, a in [
        ("מה אם הקורפוס גדל ל-million documents?",
         "numpy flat-file מספיק ל-~100K vectors בזיכרון. "
         "לmillion: מעבר ל-FAISS (approximate NN, GPU) או Qdrant/Weaviate (distributed). "
         "יש גם לפצל (shard) לפי תחום רפואי — שאלת ילד חולה לא צריכה לחפש ב-oncology. "
         "ה-retrieval code לא משתנה — רק ה-backend."),
        ("מה אם מסמך מתעדכן מדי יום?",
         "גישת incremental indexing: כל מסמך יש לו hash. "
         "כשהmash משתנה — re-chunk + re-embed רק אותו מסמך, "
         "החלף את השורות הרלוונטיות ב-.npy ו-.json. "
         "לנפחי גבוהים: מסד נתונים עם upsert-by-ID כמו Qdrant."),
        ("מה אם שואלים שאלה שלא קשורה לרפואת ילדים?",
         "המערכת תחזיר את ה-5 chunks הכי קרובים מה-corpus — "
         "שאלה על בישול תקבל חלקים רפואיים לא קשורים. "
         "פרומפט המערכת אומר לענות 'לא נמצא' אם ה-context לא רלוונטי. "
         "שיפור: הוסף classifier בשלב הראשון שבודק אם השאלה בתחום."),
    ]:
        story += qa_pair(q, a, S)

    # ══════════════════════════════════════════════════════════════════════════
    # גיליון עזר — מושגים
    # ══════════════════════════════════════════════════════════════════════════
    story += [PageBreak()]
    story += [
        Paragraph(H("גיליון עזר מהיר — מושגים שחייבים להגיד נכון"), S["h1"]),
        SP(0.1),
    ]

    terms_data = [
        [H("מושג"), H("ההגדרה הנכונה בפה"), H("טעות נפוצה להימנע ממנה")],
        ["RAG",
         H("הזנת הקשר חיצוני שאוחזר לתוך פרומפט של LLM, מה שמאלץ את התשובה להיות מושרשת במסמכים ספציפיים."),
         H("'זה חיפוש' — זה לא רק חיפוש, זה גם יצירה מושרשת.")],
        [H("Embedding"),
         H("ייצוג וקטורי של טקסט בR^384 כך שמשפטים דומים סמנטית קרובים ב-cosine distance."),
         H("'מדידת מרחק' — זה מדידת זווית (cosine), לא מרחק אוקלידי.")],
        [H("Chunking"),
         H("פיצול מסמך לחלקים בגודל שמאפשר הטמעה מדויקת ואחזור ממוקד."),
         H("'חלוקה לפסקאות' — זה אסטרטגיה שבוחרים, לא רק פסקאות.")],
        [H("Hit@k"),
         H("מדד בינארי: האם לפחות chunk אחד נכון מופיע ב-k התוצאות הראשונות?"),
         H("לא לבלבל עם Precision — Hit מדד recall, לא דיוק.")],
        [H("Precision@k"),
         H("כמה מתוך k ה-chunks שאוחזרו הם רלוונטיים? ממוצע על כל השאלות."),
         H("לא 'כמה מהתשובות נכונות' — זה מדד על ה-chunks, לא על התשובה הסופית.")],
        [H("Bi-encoder"),
         H("מודל שמקודד שאילתה ומסמך בנפרד ל-וקטורים, מה שמאפשר pre-computation."),
         H("לא לבלבל עם cross-encoder שרואה שאילתה+מסמך יחד.")],
        [H("L2 Normalisation"),
         H("חלוקת וקטור בנורמה שלו כך ש-||v||=1. Cosine similarity = dot product."),
         H("לא לומר 'normalization' בלי להסביר למה — התשובה: כדי שנוכל להשתמש ב-@.")],
        [H("Ablation Study"),
         H("ניסוי שמשנה פרמטר אחד בכל פעם כדי לבודד את השפעתו על הביצועים."),
         H("לא 'בדיקות' — ablation הוא ניסוי שיטתי, לא debug.")],
    ]
    story += [
        make_table(terms_data, [2.5*cm, 7.5*cm, 6.5*cm]),
        SP(),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # עשה / אל תעשה
    # ══════════════════════════════════════════════════════════════════════════
    story += [
        Paragraph(H("עשה ואל תעשה בהצגה"), S["h1"]),
        SP(0.1),
    ]

    do_data = [
        [H("✔ עשה"), H("✘ אל תעשה")],
        [H("דבר על ה-ChromaDB bug — זה מראה שנתקלת בבעיה אמיתית"),
         H("תגיד 'הכל עבד חלק' — מרצה לא מאמין לזה")],
        [H("הסבר את ה-ablation כניסוי שיטתי עם השערה"),
         H("תגיד סתם 'ניסיתי כמה ערכים'")],
        [H("הראה קוד אמיתי בטרמינל — לא רק סליידים"),
         H("תסתמך רק על PDF — זה לא הדגמת קוד")],
        [H("אמור 'לא ידעתי' ואחר כך הסבר מה למדת"),
         H("תמציא תשובה על מה שלא יודע — מרצה מרגיש")],
        [H("ציין את ה-tradeoff בכל החלטה (למה k=5 ולא k=3)"),
         H("תגיד 'בחרתי X כי X עובד' — תמיד יש מה לאבד")],
        [H("תדגים run אחד חי: python src/rag_system.py 'שאלה'"),
         H("תדלג על הדגמה חיה — זה הרגע הכי חזק")],
    ]
    story += [
        make_table(do_data, [8.25*cm, 8.25*cm], header_bg=NAVY),
        SP(),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # הדגמה חיה
    # ══════════════════════════════════════════════════════════════════════════
    story += [
        Paragraph(H("סקריפט הדגמה חיה — הרץ את זה לפני ההצגה"), S["h1"]),
        SP(0.1),
        Paragraph(H("פקודה לפתוח בטרמינל בתיקיית הפרויקט:"), S["body"]),
        Paragraph(
            "# הפעל שאלה אחת\n"
            "python -c \"\n"
            "from src.rag_system import answer\n"
            "import json\n"
            "r = answer('What are the discharge criteria for febrile seizure?')\n"
            "print(r['answer'])\n"
            "print('Sources:', r['sources'])\n"
            "\"",
            S["code"]),
        SP(0.1),
        Paragraph(H("הפעל את ההערכה המלאה (תוצאות שמורות ב-eval_run.log):"), S["body"]),
        Paragraph("python eval/run_eval.py --strategy fixed --k 5", S["code"]),
        SP(0.1),
        Paragraph(H("הפעל ablation:"), S["body"]),
        Paragraph("python eval/run_eval.py --ablation", S["code"]),
        SP(0.1),
        tip_box("תרגיל לפני ההצגה",
                "הרץ שאלה אחת חיה וסביר כל שורת פלט: "
                "מה chunk_id אומר, מה ה-score, ולמה התשובה מצטטת בדיוק אותם sources. "
                "אם יש שגיאה — זה לא הסוף, אמור 'שגיאה מעניינת, בוא נבין ביחד'.", S),
        SP(),
        HR(NAVY),
        SP(0.2),
        Paragraph(
            H("בהצלחה! — הפרויקט חזק, המספרים אמיתיים, והקוד עובד. "
              "הכל שנשאר הוא להסביר אותו בביטחון."),
            S["note"]),
    ]

    return story


# ── Build PDF ─────────────────────────────────────────────────────────────────
def main():
    import os
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), OUTPUT)
    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm,  bottomMargin=2*cm,
        title="מדריך הצגת הפרויקט",
        author="RAG Assignment",
    )
    S = make_styles()
    story = build_content(S)
    doc.build(story)
    print("Presentation guide written to: presentation_guide.pdf")


if __name__ == "__main__":
    main()
