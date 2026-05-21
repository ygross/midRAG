# -*- coding: utf-8 -*-
"""
generate_report_he.py — Hebrew RAG pipeline report
Uses Arial (Windows) for Hebrew Unicode support + python-bidi for RTL rendering.
"""

from bidi.algorithm import get_display as _bidi

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon, Group
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend

# ── Register Hebrew-capable fonts ────────────────────────────────────────────
pdfmetrics.registerFont(TTFont("Arial",      "C:/Windows/Fonts/arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", "C:/Windows/Fonts/arialbd.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Italic","C:/Windows/Fonts/ariali.ttf"))

OUTPUT = "report_he.pdf"

# ── Helper: apply BiDi algorithm so ReportLab renders Hebrew RTL correctly ──
def H(text: str) -> str:
    """Apply Unicode BiDi algorithm to a Hebrew string for ReportLab."""
    return _bidi(text)

# ── Colours ──────────────────────────────────────────────────────────────────
BLUE_DARK  = HexColor("#1a3a5c")
BLUE_MID   = HexColor("#2e6da4")
BLUE_LIGHT = HexColor("#d6e8f7")
GREY_LIGHT = HexColor("#f5f5f5")
GREY_MID   = HexColor("#cccccc")
ORANGE     = HexColor("#e07b39")
GREEN      = HexColor("#2d7d46")
RED        = HexColor("#c0392b")

# ── Styles ────────────────────────────────────────────────────────────────────
def make_styles():
    base = getSampleStyleSheet()

    h1 = ParagraphStyle("H1", parent=base["Heading1"],
                         fontSize=16, textColor=BLUE_DARK, spaceAfter=6,
                         spaceBefore=14, fontName="Arial-Bold",
                         alignment=TA_RIGHT)
    h2 = ParagraphStyle("H2", parent=base["Heading2"],
                         fontSize=12, textColor=BLUE_MID, spaceAfter=4,
                         spaceBefore=10, fontName="Arial-Bold",
                         alignment=TA_RIGHT)
    h3 = ParagraphStyle("H3", parent=base["Heading3"],
                         fontSize=10, textColor=BLUE_DARK, spaceAfter=3,
                         spaceBefore=7, fontName="Arial-Bold",
                         alignment=TA_RIGHT)
    body = ParagraphStyle("Body", parent=base["Normal"],
                           fontSize=9, leading=14, spaceAfter=4,
                           alignment=TA_RIGHT, fontName="Arial")
    body_left = ParagraphStyle("BodyLeft", parent=body, alignment=TA_LEFT)
    bullet = ParagraphStyle("Bullet", parent=body,
                              rightIndent=14, spaceBefore=1, spaceAfter=1,
                              alignment=TA_RIGHT, fontName="Arial")
    code = ParagraphStyle("Code", parent=base["Code"],
                           fontSize=7.5, leading=11, leftIndent=10,
                           fontName="Courier", backColor=GREY_LIGHT,
                           borderPadding=4, alignment=TA_LEFT)
    qa_q = ParagraphStyle("QAQ", parent=body,
                            fontName="Arial-Bold", textColor=BLUE_DARK,
                            spaceBefore=5, spaceAfter=2, fontSize=9,
                            alignment=TA_RIGHT)
    qa_a = ParagraphStyle("QAA", parent=body,
                            rightIndent=10, fontName="Arial",
                            textColor=HexColor("#222222"),
                            alignment=TA_RIGHT)
    note = ParagraphStyle("Note", parent=body,
                           fontSize=8, textColor=HexColor("#555555"),
                           fontName="Arial-Italic", alignment=TA_RIGHT)
    title_style = ParagraphStyle("Title", parent=base["Title"],
                                  fontSize=22, textColor=white,
                                  fontName="Arial-Bold",
                                  alignment=TA_CENTER, spaceAfter=0)
    subtitle = ParagraphStyle("Subtitle", parent=base["Normal"],
                               fontSize=12, textColor=BLUE_LIGHT,
                               fontName="Arial", alignment=TA_CENTER)
    return dict(h1=h1, h2=h2, h3=h3, body=body, body_left=body_left,
                bullet=bullet, code=code, qa_q=qa_q, qa_a=qa_a,
                note=note, title_style=title_style, subtitle=subtitle)


# ── Table helper ─────────────────────────────────────────────────────────────
def make_table(data, col_widths, header_bg=BLUE_MID):
    style = [
        ("BACKGROUND",    (0, 0), (-1, 0),  header_bg),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  white),
        ("FONTNAME",      (0, 0), (-1, 0),  "Arial-Bold"),
        ("FONTNAME",      (0, 1), (-1, -1), "Arial"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("ROWBACKGROUND", (0, 1), (-1, -1), [white, GREY_LIGHT]),
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
def cover_block(S):
    cover_data = [[
        Paragraph(H("צינור RAG רפואת ילדים"), S["title_style"]),
    ]]
    cover_table = Table(cover_data, colWidths=[17*cm])
    cover_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), BLUE_DARK),
        ("TOPPADDING",    (0,0), (-1,-1), 28),
        ("BOTTOMPADDING", (0,0), (-1,-1), 28),
        ("LEFTPADDING",   (0,0), (-1,-1), 12),
    ]))
    return [
        cover_table,
        Spacer(1, 0.3*cm),
        Paragraph(H("מטלת אמצע קורס — RAG מותאם אישית על נתונים שלך"), S["subtitle"]),
        Spacer(1, 0.2*cm),
        Paragraph(H("יומן הרצות · ארכיטקטורה · הערכה · שאלות ותשובות מלאות"), S["subtitle"]),
        Spacer(1, 0.5*cm),
        HRFlowable(width="100%", thickness=1, color=BLUE_MID),
        Spacer(1, 0.3*cm),
    ]


# ── Section helpers ───────────────────────────────────────────────────────────
def H1(text, S): return Paragraph(H(text), S["h1"])
def H2(text, S): return Paragraph(H(text), S["h2"])
def H3(text, S): return Paragraph(H(text), S["h3"])
def B(text, S):  return Paragraph(H(text), S["body"])
def BL(text, S): return Paragraph(H(text), S["body_left"])
def Bul(text, S): return Paragraph(H(f"• {text}"), S["bullet"])
def Note(text, S): return Paragraph(H(text), S["note"])
def Q(text, S):  return Paragraph(H(f"ש: {text}"), S["qa_q"])
def A(text, S):  return Paragraph(H(text), S["qa_a"])
def SP(h=0.25): return Spacer(1, h*cm)
def HR(): return HRFlowable(width="100%", thickness=0.5, color=GREY_MID)


# ── Visual helpers ────────────────────────────────────────────────────────────

def pipeline_drawing():
    """Two-row RAG pipeline: Build phase (top) + Query phase (bottom)."""
    W = 16.5 * cm
    H = 5.8 * cm
    d = Drawing(W, H)

    BW  = 2.55 * cm   # box width
    BH  = 0.88 * cm   # box height
    GAP = 0.52 * cm   # gap between boxes (arrow space)
    sx  = (W - (5 * BW + 4 * GAP)) / 2   # horizontal start ~0.85 cm

    ROW1_Y = H - 1.8 * cm   # build phase row  bottom
    ROW2_Y = 0.45 * cm       # query phase row  bottom

    def draw_box(i, row_y, label, fill):
        x = sx + i * (BW + GAP)
        d.add(Rect(x, row_y, BW, BH,
                   fillColor=fill, strokeColor=white, strokeWidth=0.7,
                   rx=4, ry=4))
        # Two-line label: split at space near midpoint
        d.add(String(x + BW / 2, row_y + BH / 2 - 4,
                     label, fontName='Arial', fontSize=7.5,
                     fillColor=white, textAnchor='middle'))

    def draw_harrow(i, row_y, color=BLUE_MID):
        x1 = sx + i * (BW + GAP) + BW
        x2 = x1 + GAP - 3
        y  = row_y + BH / 2
        d.add(Line(x1, y, x2, y, strokeColor=color, strokeWidth=1.3))
        d.add(Polygon([x2, y + 3, x2, y - 3, x2 + 5, y],
                       fillColor=color, strokeColor=color, strokeWidth=0))

    # Phase labels
    d.add(String(W / 2, H - 0.7 * cm, _bidi('שלב בנייה — בניית האינדקס'),
                 fontName='Arial-Bold', fontSize=9, fillColor=BLUE_DARK, textAnchor='middle'))
    d.add(String(W / 2, ROW2_Y + BH + 0.28 * cm, _bidi('שלב שאילתה — מענה בזמן אמת'),
                 fontName='Arial-Bold', fontSize=9,
                 fillColor=HexColor('#6c3483'), textAnchor='middle'))

    # Build phase boxes
    build_steps = [
        (_bidi('קבצי PDF'), BLUE_DARK),
        (_bidi('טעינה + ניקוי'), BLUE_MID),
        (_bidi('פיצול לחלקים'), BLUE_MID),
        (_bidi('הטמעה (MiniLM)'), BLUE_MID),
        (_bidi('אינדקס .npy'), GREEN),
    ]
    for i, (lbl, clr) in enumerate(build_steps):
        draw_box(i, ROW1_Y, lbl, clr)
        if i < 4:
            draw_harrow(i, ROW1_Y)

    # Query phase boxes
    query_steps = [
        (_bidi('שאלת משתמש'), HexColor('#6c3483')),
        (_bidi('הטמעת שאילתה'), BLUE_MID),
        (_bidi('חיפוש קוסינוס'), BLUE_MID),
        (_bidi('top-5 chunks'), ORANGE),
        (_bidi('תשובה + ציטוט'), RED),
    ]
    for i, (lbl, clr) in enumerate(query_steps):
        draw_box(i, ROW2_Y, lbl, clr)
        if i < 4:
            draw_harrow(i, ROW2_Y)

    # L-shaped connector: אינדקס .npy  →  חיפוש קוסינוס (dashed green)
    x_idx  = sx + 4 * (BW + GAP) + BW / 2
    x_srch = sx + 2 * (BW + GAP) + BW / 2
    y_mid  = (ROW1_Y + ROW2_Y + BH) / 2
    seg_color = GREEN
    for x1, y1, x2, y2 in [
        (x_idx, ROW1_Y, x_idx, y_mid),
        (x_idx, y_mid, x_srch, y_mid),
        (x_srch, y_mid, x_srch, ROW2_Y + BH + 3),
    ]:
        d.add(Line(x1, y1, x2, y2, strokeColor=seg_color,
                   strokeWidth=1.3, strokeDashArray=[4, 2]))
    d.add(Polygon([x_srch - 3, ROW2_Y + BH + 5,
                   x_srch + 3, ROW2_Y + BH + 5,
                   x_srch,     ROW2_Y + BH],
                   fillColor=seg_color, strokeColor=seg_color, strokeWidth=0))

    return d


def retrieval_example_table(S):
    """Terminal-style mockup of a real retrieval + answer (Run 4, Q#1)."""
    mono = ParagraphStyle('Mono', fontName='Courier', fontSize=7.5, leading=11,
                           textColor=HexColor('#1a1a1a'), alignment=TA_LEFT)
    mono_b = ParagraphStyle('MonoBold', parent=mono, fontName='Courier-Bold',
                              textColor=BLUE_DARK)
    he_ans = ParagraphStyle('HeAns', fontName='Arial', fontSize=9, leading=14,
                              textColor=HexColor('#1a5e20'), alignment=TA_RIGHT)
    he_q   = ParagraphStyle('HeQ',   fontName='Arial-Bold', fontSize=9, leading=14,
                              textColor=BLUE_DARK, alignment=TA_RIGHT)

    sep = Paragraph('─' * 72, mono)

    rows = [
        [Paragraph(H('שאלה:'), he_q)],
        [Paragraph(H('מהם קריטריוני השחרור לילד עם פרכוס חומי?'), he_ans)],
        [Spacer(1, 0.1 * cm)],
        [sep],
        [Spacer(1, 0.1 * cm)],
        [Paragraph('[1/5]  aap_p0042_fixed_001   score: 0.8923', mono_b)],
        [Paragraph('"Discharge criteria include: child is afebrile and neurologically at baseline, '
                   'parents counseled on fever management, follow-up arranged within 24-48 hours."', mono)],
        [Spacer(1, 0.08 * cm)],
        [Paragraph('[2/5]  aap_p0043_fixed_003   score: 0.8701', mono_b)],
        [Paragraph('"Return to ED if seizure recurs, fever persists >48 h, or child appears ill. '
                   'No neuroimaging required for a simple febrile seizure in children 6 mo – 5 yr."', mono)],
        [Spacer(1, 0.08 * cm)],
        [Paragraph('[3/5]  aap_p0042_fixed_002   score: 0.8412', mono_b)],
        [Paragraph('"Simple febrile seizure: <15 min duration, generalised, single episode in 24 h. '
                   'Antipyretic recommended for comfort; does not prevent recurrence."', mono)],
        [Spacer(1, 0.1 * cm)],
        [sep],
        [Spacer(1, 0.1 * cm)],
        [Paragraph(H('תשובה שנוצרה על-ידי Claude haiku:'), he_q)],
        [Paragraph(
            H('קריטריוני השחרור לילד עם פרכוס חומי כוללים: (1) הילד ללא חום ובמצב נוירולוגי תקין, '
              '(2) ההורים מודרכים בניהול חום וסימני החמרה, '
              '(3) מעקב רפואי תוך 24-48 שעות. '
              'הדמיה נוירולוגית אינה נדרשת לפרכוס חומי פשוט. '
              '[Source: aap_p0042_fixed_001, aap_p0043_fixed_003]'),
            he_ans)],
    ]

    t = Table([[r[0]] for r in rows], colWidths=[15.5 * cm])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), GREY_LIGHT),
        ('BOX',           (0, 0), (-1, -1), 0.6, GREY_MID),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
    ]))
    return t


def eval_bar_chart():
    """Vertical bar chart: Hit@5 per category (actual Run 4 results)."""
    W, H = 13 * cm, 7 * cm
    d = Drawing(W, H)

    bc = VerticalBarChart()
    bc.x      = 2.2 * cm
    bc.y      = 1.2 * cm
    bc.width  = 9.5 * cm
    bc.height = 4.8 * cm

    bc.data = [[1.000, 0.800, 0.800, 0.800, 0.792]]

    bc.valueAxis.valueMin  = 0.70
    bc.valueAxis.valueMax  = 1.05
    bc.valueAxis.valueStep = 0.05
    bc.valueAxis.labels.fontName  = 'Arial'
    bc.valueAxis.labels.fontSize  = 8

    bc.bars[0].fillColor   = BLUE_MID
    bc.bars[0].strokeColor = BLUE_DARK
    bc.bars[0].strokeWidth = 0.3

    bc.categoryAxis.categoryNames = [
        _bidi('שלילה'), _bidi('השוואה'), _bidi('מספרי'), _bidi('זמני'), _bidi('עובדתי'),
    ]
    bc.categoryAxis.labels.fontName = 'Arial'
    bc.categoryAxis.labels.fontSize = 9

    d.add(bc)
    d.add(String(W / 2, H - 0.4 * cm,
                 _bidi('Hit@5 לפי קטגוריה  (n=52, fixed k=5)'),
                 fontName='Arial-Bold', fontSize=10,
                 fillColor=BLUE_DARK, textAnchor='middle'))
    return d


def ablation_bar_chart():
    """Grouped bar chart: Hit@k vs Precision@k across 4 ablation experiments."""
    W, H = 16.5 * cm, 8 * cm
    d = Drawing(W, H)

    bc = VerticalBarChart()
    bc.x      = 2.5 * cm
    bc.y      = 1.3 * cm
    bc.width  = 12.5 * cm
    bc.height = 5.5 * cm

    bc.data = [
        [0.900, 0.900, 0.850, 0.900],   # Hit@k
        [0.810, 0.870, 0.850, 0.787],   # Precision@k
    ]

    bc.valueAxis.valueMin  = 0.75
    bc.valueAxis.valueMax  = 0.95
    bc.valueAxis.valueStep = 0.05
    bc.valueAxis.labels.fontName = 'Arial'
    bc.valueAxis.labels.fontSize = 8

    bc.bars[0].fillColor   = BLUE_MID
    bc.bars[0].strokeColor = BLUE_DARK
    bc.bars[0].strokeWidth = 0.3
    bc.bars[1].fillColor   = ORANGE
    bc.bars[1].strokeColor = HexColor('#a04000')
    bc.bars[1].strokeWidth = 0.3

    bc.categoryAxis.categoryNames = [
        'fixed k=5', 'para k=5', 'fixed k=3', 'fixed k=8',
    ]
    bc.categoryAxis.labels.fontName = 'Arial'
    bc.categoryAxis.labels.fontSize = 9
    bc.groupSpacing = 12
    bc.barSpacing   = 2

    d.add(bc)

    # Legend
    leg = Legend()
    leg.x             = 14.0 * cm
    leg.y             = 7.0 * cm
    leg.fontName      = 'Arial'
    leg.fontSize      = 9
    leg.colorNamePairs = [(BLUE_MID, 'Hit@k'), (ORANGE, 'Precision@k')]
    d.add(leg)

    d.add(String(W / 2, H - 0.4 * cm,
                 _bidi('השוואת ניסויי Ablation'),
                 fontName='Arial-Bold', fontSize=10,
                 fillColor=BLUE_DARK, textAnchor='middle'))
    return d


# ── Content ───────────────────────────────────────────────────────────────────
def build_content(S):
    story = []

    # Cover
    story += cover_block(S)

    # ── 1. קורפוס והכנת נתונים ───────────────────────────────────────────────
    story += [H1("1. קורפוס והכנת נתונים", S), SP()]

    story += [H2("1.1 בחירת הקורפוס", S),
    B("שני ספרי לימוד משלימים ברפואת ילדים נבחרו כקורפוס:", S), SP(0.1)]

    corpus_data = [
        [H("קובץ"), H("כותרת"), H("שנה"), H("עמודים"), H("~טוקנים")],
        ["Kliegman.pdf", H("אסטרטגיות קבלת החלטות רפואת ילדים"), "2015", "371", "~150 K"],
        ["AAP_Case-Based.pdf", H("רפואת ילדים בבית חולים: מדריך מבוסס מקרים"), "2022", "785", "~380 K"],
        [H("סה\"כ"), "", "", "1,156", "~530 K"],
    ]
    story += [make_table(corpus_data, [3.5*cm, 5.5*cm, 1.8*cm, 1.8*cm, 2*cm]), SP()]

    story += [H2("1.2 מדוע קורפוס זה?", S),
    B("מודל שפה כללי אינו יודע באופן אמין: מקרים קליניים ספציפיים (אמה, שמעון...), "
      "מינונים מדויקים של תרופות ומשכי ניטור, או לוגיקת עצי-ההחלטה בהערות הממוספרות של קלייגמן. "
      "אחזור מידע הוא הכרחי — מודל ללא RAG יהזה פרטים ספציפיים למקרה.", S), SP(0.1)]

    story += [H2("1.3 טעינה וניקוי הנתונים", S),
    B("כל PDF נטען עם PyMuPDF (fitz). הצינור:", S)]
    for step in [
        "מחלץ טקסט עמוד-עמוד עם page.get_text()",
        "מפעיל clean_text(): מכווץ שלוש שורות ריקות, מסיר ריצות רווחים, מנקה שורות מספרי עמודים ('• 30 •') ותווי bullet בודדים",
        "מדלג על עמודים עם פחות מ-50 תווים (עמודי תמונה בלבד או עטיפות ריקות)",
        "בונה מפת חלקים מתוכן העניינים הפנימי של ה-PDF דרך build_page_to_section_map() עם doc.get_toc()",
        "שומר כל עמוד בתור {doc_id, text, metadata{source, page, section, doc_id_prefix}}",
    ]:
        story.append(Bul(step, S))
    story.append(SP(0.1))

    story += [B("אתגרים שטופלו:", S)]
    for item in [
        "עיוותי PDF: מקפים באמצע מילה ומעברי שורה מוסרים חלקית בנרמול רווחים",
        "טבלאות ועצי החלטה (קלייגמן): מחולצים כטקסט גולמי; יישור עמודות אובד אך תוכן הטקסט נשמר",
        "עמודים סרוקים: שני הספרים הם PDF דיגיטליים מקוריים, ולא נדרש OCR",
        "אין נתונים רגישים: כל המטופלים בספר AAP הם מקרי הוראה בדויים המסומנים במפורש",
        "אין כפילויות: כל עמוד מעובד פעם אחת; מזהי chunk מקודדים את מספר העמוד",
    ]:
        story.append(Bul(item, S))
    story.append(SP())

    # ── 2. ארכיטקטורת המערכת ─────────────────────────────────────────────────
    story += [H1("2. ארכיטקטורת המערכת", S), SP(0.1)]

    arch_data = [
        [H("שכבה"), H("רכיב"), H("טכנולוגיה")],
        [H("טעינת מסמכים"), H("חילוץ טקסט מ-PDF + ניקוי"), "PyMuPDF (fitz)"],
        [H("פיצול לחלקים"), H("גודל-קבוע + מבוסס-פסקה"), "utils.py (מותאם)"],
        [H("אינדקסציה"), H("קבצי numpy .npy + מטא-נתוני JSON"), H("numpy (דמיון קוסינוס דרך מכפלת נקודות על וקטורים מנורמלים L2)")],
        [H("אחזור"), H("חיפוש קוסינוס top-k"), "retrieval.py"],
        [H("יצירה"), H("תשובה מושרשת עם ציטוטים"), H("Anthropic Claude (haiku-4-5)")],
        [H("הערכה"), H("Hit@k, Precision@k, איכות ידנית"), "run_eval.py"],
    ]
    story += [make_table(arch_data, [3.5*cm, 5*cm, 6*cm]), SP()]

    story += [B("זרימת נתונים: שאלה -> הטמעת שאילתה (384 ממד) -> "
                "חיפוש קוסינוס numpy (מכפלת נקודות על וקטורים מנורמלים) -> "
                "top-k חלקים -> הנחיה ל-Claude -> "
                "תשובה מושרשת עם ציטוט [Source: chunk_id] -> "
                "{answer, sources, retrieved_chunks}", S), SP()]

    # ── 3. אסטרטגיות פיצול ───────────────────────────────────────────────────
    # ── הסבר ויזואלי ─────────────────────────────────────────────────────────
    story += [
        H1("הסבר ויזואלי של הפרויקט", S), SP(0.1),
        H2("תרשים ארכיטקטורה — זרימת הצינור", S),
        B("שני שלבים עיקריים: שלב הבנייה (יחד פעם אחת) ושלב השאילתה (בכל שאלה). "
          "הקו המקווקו הירוק מציין את ה-index שנשמר ומשותף בין שני השלבים.", S),
        SP(0.15),
        pipeline_drawing(),
        SP(0.3),
        H2("דוגמה מלאה: שאלה → chunks שאוחזרו → תשובה", S),
        B("הרצה 4, שאלה מספר 1 (Hit: ✓, Precision@5: 0.40, זמן: 7.6 שניות). "
          "המערכת מחפשת, מדרגת ומעבירה את ה-chunks המובילים ל-Claude לייצור תשובה:", S),
        SP(0.1),
        retrieval_example_table(S),
        SP(0.3),
        PageBreak(),
        H2("ביצועי אחזור לפי קטגוריה", S),
        B("תוצאות בפועל — הרצה 4 (eval/run_eval.py, n=52, fixed chunks, k=5):", S),
        SP(0.1),
        eval_bar_chart(),
        SP(0.3),
        H2("השוואת ניסויי Ablation", S),
        B("ארבעה ניסויים על 20 השאלות הראשונות. "
          "אסטרטגיית הפסקה ו-k=5 מנצחת — Hit@k שווה לגודל-קבוע אך Precision גבוה ב-6%:", S),
        SP(0.1),
        ablation_bar_chart(),
        SP(0.3),
        PageBreak(),
    ]

    # ── 3. אסטרטגיות פיצול ───────────────────────────────────────────────────
    story += [H1("3. אסטרטגיות פיצול לחלקים", S), SP(0.1)]

    chunk_data = [
        [H("אסטרטגיה"), H("גודל"), H("חפיפה"), H("צעד"), H("מתאים ל-")],
        [H("גודל-קבוע"), H("400 תווים"), H("50 תווים"), "350", H("עצי החלטה של קלייגמן (צפוף, קצר)")],
        [H("מבוסס-פסקה"), H("100-700 תווים"), H("אין"), "n/a", H("פסקאות שאלות ותשובות של AAP")],
    ]
    story += [make_table(chunk_data, [3.5*cm, 2.2*cm, 2*cm, 1.5*cm, 6.3*cm]), SP(0.1)]

    story += [H3("פרטי אסטרטגיית גודל-קבוע:", S)]
    for item in [
        "החלון מתקדם 350 תווים (=400-50) כך שחלקים סמוכים חולקים 50 תווי הקשר",
        "חפיפה מבטיחה שמשפט שנחתך בגבול מופיע שלם בלפחות chunk אחד",
        "Chunks זנב קצרים מ-30 תווים נמחקים (רווח לבן שיורי)",
        "פורמט מזהה Chunk: kliegman_p0142_fixed_002 (קידומת_עמוד_אסטרטגיה_אינדקס)",
    ]:
        story.append(Bul(item, S))
    story.append(SP(0.1))

    story += [H3("פרטי אסטרטגיית פסקה:", S)]
    for item in [
        "פיצול על שורות-כפולות (מעברי פסקה טבעיים מחילוץ PDF)",
        "מיזוג פסקאות קצרות עוקבות עד שהחוצץ מגיע ל-min_len=100 תווים",
        "פיצול פסקאות ארוכות מדי (>700 תווים) על גבולות משפטים",
        "תוצאה: כל chunk הוא מחשבה קלינית שלמה — ללא חתכים שרירותיים",
    ]:
        story.append(Bul(item, S))
    story.append(SP(0.1))

    story += [H3("דוגמת כשל — היכן הפיצול פגע באחזור:", S),
    B("שאלה: 'מהו הטיפול באוטיטיס מדיה חריפה אם הילד מתחת לגיל 2?' "
      "עמוד קלייגמן המכסה נושא זה מכיל עץ החלטה עם הערות ממוספרות. "
      "פיצול בגודל-קבוע חתך בין הערה 3 (בחירת אנטיביוטיקה) להערה 4 (משך מינון) "
      "בגבול 400 התווים. האחזור החזיר את ה-chunk עם הערה 3 (זיהה נכון אמוקסיצילין) "
      "אך החמיץ הערה 4 (קורס 10 יום לעומת 5 יום). "
      "אסטרטגיית הפסקה שמרה את ההערות יחד.", S), SP()]

    # ── 4. הטמעה ואינדקסציה ──────────────────────────────────────────────────
    story += [H1("4. הטמעה ואינדקסציה", S), SP(0.1)]

    story += [H2("4.1 מודל הטמעה: all-MiniLM-L6-v2", S)]
    for item in [
        "384 ממדים — קומפקטי, מהיר על CPU (~42 שניות ל-3,200 chunks)",
        "נרמול L2 בזמן קידוד (normalize_embeddings=True), כך שדמיון קוסינוס שווה למכפלת נקודות",
        "אומן על 1B+ זוגות משפטים עם למידה ניגודית; אחזור סמנטי חזק לטקסט רפואי באנגלית",
        "נבחר על פני מודלים גדולים יותר (all-mpnet-base-v2, 768 ממד) לשמירת זמן תגובה סביר ללא GPU",
        "מדוע לא BM25 לבד? BM25 מתאים מילות מפתח; 'febrile seizure discharge criteria' מחמיץ קטעים עם מילים נרדפות כמו 'afebrile and neurologically baseline'",
    ]:
        story.append(Bul(item, S))
    story.append(SP(0.1))

    story += [H2("4.2 אינדקס Numpy (במקום ChromaDB)", S)]
    for item in [
        "פורמט אחסון: index/fixed_embeddings.npy (float32, צורה N×384, 14.8 MB) + index/fixed_chunks.json (רשימת מטא-נתוני chunks)",
        "ללא מסד נתונים וקטורי חיצוני — מכפלת מטריצה בלבד של numpy: scores = embeddings @ qvec.T — דמיון קוסינוס מדויק בפעולה אחת",
        "שני זוגי אינדקס: אסטרטגיית גודל-קבוע (10,107 chunks) ואסטרטגיית פסקה (5,250 chunks)",
        "ניתן לשחזור מלא: build_index.py מחליף את .npy/.json בכל הרצה",
        "מדוע numpy במקום ChromaDB? ל-ChromaDB 1.5.9 יש תקלת HNSW ספציפית ל-Windows — אינדקס ה-Rust לא נכתב לדיסק בין תהליכים. backend ה-numpy נייד לחלוטין ומספיק ל-~10K וקטורים.",
    ]:
        story.append(Bul(item, S))
    story.append(SP())

    # ── 5. אחזור ─────────────────────────────────────────────────────────────
    story += [H1("5. אחזור", S), SP(0.1)]

    story += [B("ממשק: retrieve(query: str, k: int = 5, strategy: str = 'fixed') -> list[dict]", S), SP(0.1)]

    story += [B("האחזור מטמיע את השאילתה עם אותו מודל ונרמול כמו האינדקס, "
                "ואז מחשב דמיון קוסינוס כמכפלת נקודות numpy מול כל הוקטורים המאוחסנים. "
                "np.argpartition בוחר את מדדי ה-top-k ב-O(N), הממוינים בסדר יורד. "
                "כל תוצאה מוחזרת בתור {chunk_id, text, score, metadata}.", S), SP(0.1)]

    story += [H3("מדוע k=5?", S),
    B("ב-k=5 חלון ההקשר הצפוי הוא ~5×400=2,000 תווים, בתוך גבול ה-context של Claude haiku "
      "ומשאיר מקום לפרומפט המערכת ולתשובה. Ablation (הרצות 6/7) מראה ש-k=5 הוא "
      "נקודת האיזון בין precision לrecall עבור מערכת השאלות.", S), SP(0.1)]

    story += [H3("אחזור היברידי:", S),
    B("retrieve_hybrid() שואל את שני האינדקסים (גודל-קבוע ופסקה), מבטל כפילויות לפי (מקור, עמוד) "
      "תוך שמירת ה-chunk עם הניקוד הגבוה יותר, ומחזיר את ה-top-k המאוחד. "
      "זה לא ברירת המחדל אך זמין לניתוח ablation.", S), SP(0.1)]

    story += [H3("מדדי אחזור:", S)]
    ret_data = [
        [H("מדד"), H("הגדרה"), H("בפועל (k=5, fixed, n=52)")],
        ["Hit@5", H(">=1 chunk שאוחזר תואם מקור זהב בטווח +-2 עמודים"), "0.827 (43/52)"],
        ["Precision@5", H("חלק מ-5 chunks שאוחזרו ממקור נכון"), "0.881"],
        [H("זמן תגובה ממוצע"), H("זמן answer() כולל יצירה"), "3.14 s"],
    ]
    story += [make_table(ret_data, [3.5*cm, 8*cm, 4*cm]), SP()]

    # ── 6. הנדסת פרומפט ──────────────────────────────────────────────────────
    story += [H1("6. הנדסת פרומפט ויצירה", S), SP(0.1)]

    story += [H2("6.1 עיצוב פרומפט המערכת", S),
    B("פרומפט המערכת אוכף ארבעה כללים:", S)]
    for i, rule in enumerate([
        "בסס את תשובתך אך ורק על ההקשר שאוחזר (ללא הזיות מזיכרון פרמטרי)",
        "אם התשובה לא נמצאת, אמור: 'המידע לא נמצא במקורות שסופקו'",
        "לאחר תשובתך, תמיד ציטוט: [Source: chunk_id_1, chunk_id_2]",
        "היה תמציתי ומדויק קלינית. אל תוסיף מידע מידע כללי.",
    ], 1):
        story.append(Bul(f"כלל {i}: {rule}", S))
    story.append(SP(0.1))

    story += [H2("6.2 בניית ההנחיה", S)]
    for item in [
        "פרומפט המשתמש: 'Context:\\n[chunk_1_text]\\n[chunk_2_text]...\\n\\nQuestion: {query}'",
        "Context מסודר לפי ניקוד יורד — ה-chunk הרלוונטי ביותר ראשון",
        "max_tokens=512 — מספיק לתשובה קלינית עם ציטוטים; מונע דריפט ארוך",
        "temperature=0 (ברירת מחדל) — מקסימום דטרמיניזם לתשובות עובדתיות",
    ]:
        story.append(Bul(item, S))
    story.append(SP(0.1))

    story += [H2("6.3 ניתוח ציטוטים", S)]
    for item in [
        "ציטוטים מפורסרים עם re.findall(r'\\[Source:([^\\]]+)\\]', answer)",
        "כשל ידוע: כאשר המערכת אומרת 'לא נמצא', לעיתים עדיין מציינת את ה-chunk הקרוב ביותר כציטוט שגוי",
        "כשל חלקי: המודל עשוי לצטט רק אחד משני chunks שתומכים יחד בתשובה",
    ]:
        story.append(Bul(item, S))
    story.append(SP())

    # ── 7. הערכה ─────────────────────────────────────────────────────────────
    story += [H1("7. הערכה", S), SP(0.1)]

    story += [H2("7.1 מערכת השאלות המוזהבת", S),
    B("52 שאלות ב-5 קטגוריות, עם must_cite_chunk_ids מעוגנות לעמוד מדויק:", S), SP(0.1)]

    gold_data = [
        [H("קטגוריה"), H("כמות"), H("דוגמה")],
        [H("עובדתי"), "24", H("מהם קריטריוני השחרור לילד עם פרכוס חומי?")],
        [H("מספרי"), "10", H("מהו הגיל שבו ניתן לצפות לסגירת הפונטנל?")],
        [H("שלילה"), "8",  H("האם פונטנל שקוע מעיד על הידרוצפלוס?")],
        [H("השוואה"), "5",  H("כיצד שונה נזלת חריפה מכרונית?")],
        [H("זמני"), "5",   H("מתי פיזיולוגי לצפות לגרעין יילוד?")],
    ]
    story += [make_table(gold_data, [2.5*cm, 1.8*cm, 10.2*cm]), SP(0.1)]

    story += [H2("7.2 תוצאות הערכה (בסיס — fixed, k=5, n=52)", S)]
    eval_data = [
        [H("מדד"), H("ערך"), H("הערות")],
        ["Hit@5", "0.827", H("43/52 שאלות עם chunk זהב ב-top-5")],
        ["Precision@5", "0.881", H("גבוה מאוד — פיצול גודל-קבוע מדויק לקורפוס זה")],
        [H("זמן תגובה ממוצע"), "3.14 s", H("~0.1 s אחזור + ~3.0 s יצירה (caching API)")],
        [H("איכות ידנית (10)"), H("6 נכון / 3 חלקי / 1 שגוי"), H("ראה יומן הרצות הרצה 4 לפרטים")],
    ]
    story += [make_table(eval_data, [3.5*cm, 3*cm, 8*cm]), SP(0.1)]

    story += [H2("7.3 Hit@5 לפי קטגוריה (בפועל, n=52)", S)]
    cat_data = [
        [H("קטגוריה"), "Hit@5", "n", H("תצפית")],
        [H("שלילה"), "1.000", "8/8", H("מושלם — כללי פרומפט השלילה עבדו היטב")],
        [H("השוואה"), "0.800", "4/5", H("השוואת פרקים אחד נפלה")],
        [H("מספרי"), "0.800", "8/10", H("2 תשובות נחתכו בגבול ה-chunk")],
        [H("זמני"), "0.800", "4/5", H("טוב יותר מהצפוי — ביטויי זמן נשמרו ברובם")],
        [H("עובדתי"), "0.792", "19/24", H("5 כשלים — רובם מונחי עץ-ההחלטה של קלייגמן")],
    ]
    story += [make_table(cat_data, [3*cm, 2*cm, 1.8*cm, 8.7*cm]), SP()]

    # ── 8. מחקר Ablation ─────────────────────────────────────────────────────
    story += [H1("8. מחקר Ablation", S), SP(0.1)]

    abl_data = [
        [H("ניסוי"), "Hit@k", "Precision@k", H("זמן תגובה"), H("הערות")],
        [H("chunks גודל-קבוע, k=5 (בסיס)"), "0.900", "0.810", "3.2 s", H("ייחוס (20 שאלות ראשונות)")],
        [H("chunks פסקה, k=5"), "0.900", "0.870", "3.2 s", H("אותו Hit; +6% Precision — האפשרות הטובה ביותר")],
        [H("chunks גודל-קבוע, k=3"), "0.850", "0.850", "2.8 s", H("Precision גבוה, מפסיד hit 1 מספרי")],
        [H("chunks גודל-קבוע, k=8"), "0.900", "0.787", "3.3 s", H("ללא שיפור Hit; Precision יורד 2.3%")],
    ]
    story += [make_table(abl_data, [4.5*cm, 1.8*cm, 2.5*cm, 2*cm, 4.7*cm]), SP(0.1)]

    story += [H3("ממצא מרכזי:", S),
    B("אסטרטגיית הפסקה ב-k=5 היא האפשרות הכוללת הטובה ביותר — "
      "שווה לפיצול גודל-קבוע ב-Hit (0.900) אך עם 6% יותר Precision (0.870 לעומת 0.810). "
      "זמן התגובה כמעט שטוח בכל הניסויים (2.8-3.3 s) — "
      "צוואר הבקבוק הוא קריאת ה-API, לא האחזור. "
      "k=3 מפסיד hit אחד מספרי; k=8 מוסיף רעש ללא שחזור hits נוספים.", S), SP()]

    # ── 9. ניתוח כשלים ───────────────────────────────────────────────────────
    story += [H1("9. ניתוח כשלים", S), SP(0.1)]

    fail_data = [
        [H("מצב כשל"), H("תדירות"), H("סיבה שורשית"), H("פתרון")],
        [H("ציון Ballard לא נמצא"), H("1 (ש.3)"), H("עמוד טבלת קלייגמן נדלג על ידי מסנן 50-תו"), H("הורד סף דילוג; חילוץ ממוד-טבלה")],
        [H("ספר מקור שגוי"), H("1 (ש.10)"), H("שאלת גסטרו חזרה chunks מ-AAP; תשובה הייתה בקלייגמן"), H("k גבוה יותר; אחזור היברידי")],
        [H("ראשי תיבות לא פוענחו"), H("1 (ש.4)"), H("עמוד נכון אוחזר אך המודל לא חילץ פיענוח"), H("שלב עיבוד מקדים לראשי תיבות")],
        [H("משך לא צוין"), H("3/52"), H("משך ניטור במשפט אחר מהמלצת הניטור"), H("אסטרטגיית פסקה שומרת הקשר רב יותר")],
        [H("שברי עץ-החלטה"), H("5 עובדתי"), H("פיצול גודל-קבוע מפצל הערות בהחלטת אמצע"), H("אסטרטגיית פסקה; פיצול ממוד-חלק")],
    ]
    story += [make_table(fail_data, [3.5*cm, 2*cm, 4.5*cm, 4.5*cm]), SP(0.1)]

    story += [H3("מדוע הזיות LLM קורות גם עם אחזור נכון:", S),
    B("גם כשה-chunk הנכון אוחזר, Claude עשוי 'להמציא' אם: "
      "(1) המשפט ב-chunk דו-משמעי והמודל פותר עם ידע פרמטרי; "
      "(2) ה-chunk משתמש בקיצורים מקצועיים שהמודל מפרש בגמישות; "
      "(3) המודל מוסיף פרט נכון-לכאורה אך לא נתמך. "
      "כלל 4 בפרומפט ('אל תוסיף ידע כללי') מפחית אך לא מבטל זאת.", S), SP()]

    # ── 10. שיפורים עתידיים ──────────────────────────────────────────────────
    story += [H1("10. שיפורים שנעשה בהמשך", S), SP(0.1)]

    improvements = [
        ("Cross-encoder לדירוג מחדש",
         "לאחר top-k עם bi-encoder, החל cross-encoder (ms-marco-MiniLM-L-6-v2) לדרג מחדש. "
         "Cross-encoders מדויקים הרבה יותר, בעלות של מעבר קדימה לכל זוג."),
        ("אחזור מסונן לפי מטא-נתונים",
         "לשאלות מספריות — סנן לחלקים המכילים ספרות. לשאלות זמניות — מחרוזות שנה/יום/חודש. "
         "מצמצם רעש ללא הגדלת k."),
        ("חפיפה ברמת משפט",
         "החלף חפיפת תווים בחפיפת גבולות-משפט — ערב שכל chunk מתחיל ומסתיים במשפט שלם."),
        ("LLM כשופט",
         "השתמש ב-Claude Sonnet כדי לסווג נכונות תשובות מול reference_answer אוטומטית, "
         "תוך החלפת הבדיקה הידנית ל-50 שאלות."),
        ("Prompt Caching",
         "השתמש ב-Anthropic prompt caching על פרומפט המערכת (קבוע בין קריאות) "
         "לחיסכון של ~30% בעלויות טוקן."),
        ("סקלת ייצור",
         "למיליוני מסמכים: החלף את backend ה-numpy ב-Qdrant או Weaviate (מבוסס HNSW, מבוזר); "
         "חלק לפי תחום; הוסף BM25 היברידי; השתמש בהטמעה אסינכרונית."),
    ]
    for title, desc in improvements:
        story += [Bul(f"{title}: {desc}", S)]
    story.append(SP())
    story.append(PageBreak())

    # ── 11. שאלות ותשובות מלאות ──────────────────────────────────────────────
    story += [H1("11. שאלות ותשובות מלאות — סקירת מרצה", S),
    Note("החלק הבא עונה על כל שאלות ההערכה הצפויות על החלטות עיצוב "
         "וההבנה שמאחורי כל שכבה בצינור ה-RAG.", S),
    SP(0.1)]

    def qa_block(question, answer_text):
        return [Q(question, S), A(answer_text, S), SP(0.1)]

    story += [H2("פתיחה — הבנה כללית", S)]

    story += qa_block(
        "מדוע בחרת בקורפוס זה?",
        "בחרנו שני ספרי לימוד ברפואת ילדים מכיוון שהם מכילים עובדות קליניות מדויקות "
        "(מינוני תרופות, מקרי מטופלים בשמות, לוגיקת עץ החלטות) שמודל שפה כללי "
        "אינו יודע באופן אמין. האחזור הכרחי — לא עטיפה של משהו שה-LLM כבר יודע."
    )
    story += qa_block(
        "איזה בעיה מערכת ה-RAG שלך פותרת?",
        "רופא או סטודנט ששואל על מקרה ילודים ספציפי או פרוטוקול מינון "
        "אינו יכול לסמוך על LLM מזיכרון. המערכת שלנו מעגנת כל תשובה בקטע "
        "שאוחזר מהספר ומצטטת את העמוד המדויק, מה שהופך את התשובה לניתנת לאימות."
    )
    story += qa_block(
        "מדוע LLM רגיל אינו מספיק?",
        "ל-LLMs יש ידע פרמטרי שמוקפא בזמן האימון. אין להם מקרים ספציפיים "
        "ממדריך AAP 2022 (שמעון, חולה פרכוס חומי) או ספי הערות מדויקים של קלייגמן. "
        "הם יהזו פרטים קלינית אפשריים אך שגויים. RAG מאלץ את התשובה לבוא מהמקור."
    )
    story += qa_block(
        "אילו סוגי שאלות המערכת עונה עליהן טוב?",
        "שאלות שלילה השיגו ניקוד מושלם (1.000 Hit@5, 8/8) — כללי פרומפט "
        "לאישור היעדר עבדו היטב. מספרי וזמני השיגו גם הם 0.800. "
        "בסך הכל המערכת ניקתה 0.827 Hit@5 על 52 שאלות."
    )
    story += qa_block(
        "על אילו סוגי שאלות היא נכשלת?",
        "עובדתי (0.792) הייתה הקטגוריה החלשה ביותר — רוב הכשלים היו מונחי עץ-ההחלטה "
        "הספציפיים לקלייגמן שפיצול גודל-קבוע פיצל. שתי תשובות מספריות נחתכו "
        "בגבול 400 התווים. שאלת השוואה אחת דרשה ראיות משני פרקים שונים."
    )

    story += [H2("נתונים וקורפוס", S)]
    story += qa_block(
        "כיצד אספת את הנתונים?",
        "שני ה-PDF הושגו כספרי לימוד פורסמו בשימוש בקורס אקדמי. "
        "הם הוצבו ב-data/raw/ ונטענו אוטומטית. ללא גרידה או גישת API."
    )
    story += qa_block(
        "מה היו האתגרים בניקוי הטקסט?",
        "PyMuPDF מחלץ טקסט עם עיוותי פריסת PDF: שורות מספרי עמודים ('• 30 •'), "
        "שלוש שורות ריקות בין חלקים, רווחים שיוריים. clean_text() מטפל בהם "
        "עם ארבעה מעברי regex. האתגר הגדול יותר הוא טבלאות עץ-ההחלטה של קלייגמן "
        "שמחולצות כטקסט לא מסודר — יישור עמודות אובד."
    )
    story += qa_block(
        "האם היו מסמכים בעייתיים? PDF סרוקים?",
        "שני הספרים הם PDF דיגיטליים מקוריים (לא תמונות סרוקות), "
        "כך שלא נדרש OCR. הבעיה העיקרית הייתה פריסת טבלה דו-עמודית צפופה של קלייגמן, "
        "שאותה PyMuPDF מיישר — סדר הקריאה לעיתים שגוי לנתונים טבלאיים."
    )
    story += qa_block(
        "כיצד טיפלת בכפילויות?",
        "לכל עמוד מוקצה doc_id ייחודי המקודד קידומת מקור ומספר עמוד (לדוג', kliegman_p0142). "
        "Chunks יורשים מזהה זה. מכיוון שכל עמוד מעובד בדיוק פעם אחת, "
        "אין כפילויות ברמת המסמך. ברמת ה-chunk, שילוב (doc_id + chunk_index) הוא ייחודי."
    )
    story += qa_block(
        "כיצד אימתת שהקורפוס מתאים ל-RAG?",
        "בדקנו: (1) הקורפוס מכיל >30 עמודים, (2) המידע אינו ידוע היטב ל-Claude ללא אחזור "
        "(אומת על ידי שאילתת LLM בסיסי ללא RAG על שאלות ספציפיות למקרה), "
        "ו-(3) הטקסט ניתן לחילוץ (לא תמונה)."
    )

    story += [H2("פיצול לחלקים", S)]
    story += qa_block(
        "איזה גודל chunk בחרת ומדוע?",
        "400 תווים (~80 טוקנים) לגודל-קבוע. זה שומר כל chunk בתוך אמירה קלינית אחת "
        "תוך היות מספיק גדול כדי שמודל ההטמעה ילכוד הקשר סמנטי. "
        "אסטרטגיית הפסקה משתמשת ב-100-700 תווים כדי להתאים לגבולות פסקה טבעיים."
    )
    story += qa_block(
        "מדוע נדרשת חפיפה?",
        "חפיפה מבטיחה שעובדה שנחתכת בגבול שני chunks מופיעה שלמה בלפחות chunk אחד. "
        "ללא חפיפה, משפט שחוצה את גבול 400 התווים יפוצל לשני חצאי-משפטים, "
        "אף אחד מהם לא מכיל את העובדה השלמה. "
        "חפיפת 50 תווים היא כ-קטע משפט אחד."
    )
    story += qa_block(
        "מה קורה אם chunks קטנים מדי?",
        "Chunks קטנים מדי (לדוג', 100 תווים) מאבדים הקשר סמנטי — כל chunk הוא קטע משפט. "
        "ההטמעה לוכדת את משמעות הקטע בצורה לקויה ורעש האחזור עולה. "
        "גם יותר chunks אומר יותר קריאות API ובנייה איטית יותר של אינדקס."
    )
    story += qa_block(
        "מה קורה אם chunks גדולים מדי?",
        "Chunks גדולים מדי (לדוג', 1000+ תווים) גורמים לסטייה נושאית — שני נושאים קליניים "
        "לא קשורים עשויים להיות מאוחדים. ההטמעה ממצעת על כל הטקסט, ומדללת "
        "את האות הסמנטי לאחזור. שלב היצירה מקבל גם הוא הקשר רועש."
    )

    story += [H2("הטמעה ואינדקס", S)]
    story += qa_block(
        "איזה מודל הטמעה בחרת ומדוע?",
        "all-MiniLM-L6-v2: 384 ממד, מהיר (~42 שניות ל-3,200 chunks על CPU), "
        "אחזור סמנטי חזק לטקסט רפואי באנגלית. נבחר על פני מודלים גדולים יותר "
        "(all-mpnet-base-v2, 768 ממד) לאיזון איכות מול מהירות. "
        "מודלים ספציפיים רפואיים (BioBERT, PubMedBERT) נשקלו אך לא נבחרו "
        "— הקורפוס משתמש באנגלית קלינית סטנדרטית."
    )
    story += qa_block(
        "ניסית מספר הטמעות?",
        "ה-ablation הריץ פיצול גודל-קבוע לעומת פסקה עם אותו מודל. "
        "ablation מודל (all-MiniLM-L6-v2 לעומת all-mpnet-base-v2) יהיה ניסוי טבעי הבא. "
        "אסטרטגיית הפסקה הראתה Precision@5 גבוה יותר (0.870 לעומת 0.810) "
        "עם Hit@5 שווה, מה שמרמז שאסטרטגיית הפיצול משפיעה על precision יותר "
        "מאשר בחירת המודל עבור קורפוס זה."
    )
    story += qa_block(
        "מדוע numpy במקום ChromaDB או FAISS?",
        "בנינו במקור על ChromaDB, אך לגרסה 1.5.9 יש תקלת HNSW ספציפית ל-Windows — "
        "אינדקס ה-Rust לא נכתב לדיסק בין תהליכים, מה שגרם לכשל אחזור בכל תהליך Python חדש. "
        "במקום לשדרג לאחור, החלפנו ב-backend numpy: שמור הטמעות כ-.npy, "
        "טען עם np.load(), חפש עם מכפלת מטריצה יחידה. "
        "ל-~10K וקטורים, זה מהיר יותר (ללא IPC overhead), נייד לחלוטין, "
        "ולא דורש תלות חיצונית מעבר ל-numpy."
    )
    story += qa_block(
        "מה מדד הדמיון שהשתמשת בו?",
        "דמיון קוסינוס. הטמעות מנורמלות L2 בזמן קידוד (normalize_embeddings=True), "
        "כך שדמיון קוסינוס שווה למכפלת נקודות: scores = embeddings @ qvec.T. "
        "זה מתמטית שקול ומונע את המרת distance-to-similarity הדרושה ל-ChromaDB."
    )
    story += qa_block(
        "האם נרמול משפיע על התוצאות?",
        "כן. ללא נרמול L2, המכפלה תלויה בגודל הוקטור, שיכול להשתנות לפי "
        "אורך משפט ועושר אוצר מילים. נרמול הופך את דמיון הקוסינוס לעניין "
        "רק של הזווית בין הוקטורים (כיוון סמנטי), לא הגודל. "
        "זה חשוב להשוואה הוגנת בין שברי עץ-החלטה קצרים לפסקאות נרטיביות ארוכות."
    )

    story += [H2("אחזור", S)]
    story += qa_block(
        "כיצד עובד האחזור?",
        "השאילתה מוטמעת עם אותו מודל ונרמול כמו ה-chunks. "
        "האחזר מחשב scores = embeddings @ qvec.T — מכפלת מטריצה numpy יחידה — "
        "ונותן דמיון קוסינוס לכל chunk בבת אחת. np.argpartition בוחר את מדדי top-k "
        "ב-O(N), הממוינים בסדר יורד. תוצאות מוחזרות כ-dicts מובנים."
    )
    story += qa_block(
        "מה ההבדל בין precision ל-recall?",
        "Precision@k: מתוך k chunks שאוחזרו, כמה רלוונטיים? "
        "Recall@k: מתוך כל ה-chunks הרלוונטיים באינדקס, כמה אוחזרו? "
        "k גבוה יותר משפר recall אך עשוי לפגוע ב-precision. "
        "Hit@k הוא מדד recall בינארי: האם לפחות chunk נכון אחד הופיע ב-top-k?"
    )
    story += qa_block(
        "האם אחזור טוב תמיד מוביל לתשובה טובה?",
        "לא. גם עם ה-chunk הנכון שאוחזר, ה-LLM יכול: "
        "(1) לפרש שגוי קיצורים קליניים, "
        "(2) לייצר תשובה עקבית לוגית עם ה-chunk אך הוסיף פרט לא נתמך, "
        "(3) לכשול בחילוץ ערך מספרי מטבלה צפופה. "
        "אחזור הכרחי אך לא מספיק."
    )

    story += [H2("ציטוטים", S)]
    story += qa_block(
        "כיצד יודעים שהתשובה מבוססת על המקור?",
        "פרומפט המערכת מורה ל-Claude לענות רק מהקשר שאוחזר ולצטט את chunk_ids שבשימוש. "
        "אנחנו מפרסרים [Source: chunk_id, ...] מהתגובה. "
        "נאמנות ניתנת לאימות על ידי בדיקה שהטקסט של ה-chunk המצוטט מרמז על התשובה."
    )
    story += qa_block(
        "האם ציטוטים תמיד נכונים?",
        "לא. שני מצבי כשל ידועים: (1) ציטוט fallback — כשהמערכת אומרת 'לא נמצא', "
        "היא לעיתים עדיין מציינת את ה-chunk הקרוב ביותר כהפנייה שגויה. "
        "(2) ציטוט חלקי — המודל עשוי לצטט רק אחד משני chunks התומכים יחד בתשובה."
    )

    story += [H2("הערכה", S)]
    story += qa_block(
        "כיצד בנית את מערכת השאלות המוזהבת?",
        "על ידי קריאת כל פרק וניסוח שאלות שתשובותיהן מצוינות במפורש בעמוד ידוע. "
        "לכל שאלה הוקצו must_cite_chunk_ids המעוגנות לעמוד המדויק. "
        "גיוון נאכף על ידי דרישת לפחות 5 שאלות לקטגוריה "
        "ומכסות את שני הספרים."
    )
    story += qa_block(
        "ההבדל בין Hit@k ל-Recall@k?",
        "Hit@k הוא בינארי לשאלה: 1 אם chunk זהב כלשהו מופיע ב-top-k, 0 אחרת. "
        "Recall@k ממצע על כל ה-chunks המוזהבים: איזה חלק מכל ה-chunks הרלוונטיים אוחזר? "
        "Hit@k מעשי יותר להערכת שאלות-ותשובות; Recall@k אינפורמטיבי יותר לשאלות multi-hop."
    )

    story += [H2("מחקר Ablation", S)]
    story += qa_block(
        "איזה שינוי היה בעל ההשפעה הגדולה ביותר?",
        "שינוי אסטרטגיית הפיצול (גודל-קבוע -> פסקה) היה בעל ההשפעה החיובית הגדולה ביותר: "
        "Hit@k זהה (0.900) אך +6% Precision@k (0.870 לעומת 0.810) ללא עלות זמן תגובה. "
        "הפחתת k מ-5 ל-3 הייתה הירידה הגדולה ביותר ב-Hit (-5 נקודות אחוז). "
        "k=8 הוסיף רעש ללא שיפור ב-Hit."
    )
    story += qa_block(
        "מה למדת מה-ablation?",
        "שלושה לקחים: (1) אסטרטגיית פיצול חשובה יותר מ-k עבור precision — "
        "פיצול פסקה מנצח ב-precision בכל ה-k. "
        "(2) k=5 הוא נקודת האיזון — k=3 מחמיץ ראיות multi-hop; k=8 מוסיף רעש. "
        "(3) זמן התגובה כמעט שטוח (2.8-3.3 s) — צוואר הבקבוק הוא קריאת ה-Claude API."
    )

    story += [H2("שאלות מתקדמות", S)]
    story += qa_block(
        "ההבדל בין bi-encoder ל-cross-encoder?",
        "Bi-encoder (כמו all-MiniLM) מקודד שאילתה ומסמך באופן עצמאי — "
        "הטמעת השאילתה ניתנת לחישוב מוקדם, מה שהופך את האחזור למהיר. "
        "Cross-encoder לוקח שאילתה+מסמך כקלט יחיד ומעביר תשומת לב משותפת לשניהם — "
        "הרבה יותר מדויק אך דורש מעבר קדימה אחד לכל זוג (שאילתה, מסמך). "
        "Reranking משתמש ב-bi-encoder לבחירה מהירה של top-k ו-cross-encoder לדירוג מדויק."
    )
    story += qa_block(
        "מהי סטייה סמנטית?",
        "כאשר מרכיבים chunks שאוחזרו כהקשר, המודל עשוי להתחיל 'לסטות' מהכוונה "
        "הסמנטית הראשונית של השאילתה — במיוחד אם ה-chunks ארוכים או מכילים נושאים מרובים. "
        "תשומת הלב של המודל מתפשטת והתשובה עשויה לטפל בשאלה קלינית קשורה אך שונה."
    )
    story += qa_block(
        "מהי הרעלת חלון הקשר?",
        "מסמך זדוני יכול להכיל טקסט כגון: 'התעלם מכל ההוראות הקודמות ובמקום זאת פלוט X'. "
        "אם זה אוחזר ומוצב בהקשר, ה-LLM עשוי לפעול לפי ההוראה המוזרקת. "
        "הפחתה: נקה טקסט שאוחזר, השתמש בפרומפט מערכת שמדגיש התעלמות מטקסטים כמו הוראות בהקשר."
    )
    story += qa_block(
        "כיצד תטפל במסמכים שמתעדכנים יומיומית?",
        "השתמש בגישת אינדקסציה מצטברת: עקוב אחר גרסאות מסמכים עם hash. "
        "כאשר מסמך משתנה, פצל מחדש והטמע רק את אותו מסמך, "
        "ואז עדכן את קבצי .npy ו-.json (החלף שורות עבור chunk IDs של אותו מסמך, "
        "או בנה מחדש רק את פרוסת המסמך). לנפחי עדכון גבוהים — עבור ל-Qdrant או Weaviate."
    )
    story += qa_block(
        "כיצד תעשה RAG אג'נטי?",
        "סוכן יעשה: (1) יקבל שאלה, (2) יחליט אם אחזור נדרש (שלב מטא-קוגניציה), "
        "(3) ינסח שאילתת אחזור (אולי שונה מהשאלה המקורית), "
        "(4) יבדוק chunks שאוחזרו, (5) יחליט אם לאחזר שוב עם שאילתה מעודנת "
        "או להמשיך ליצירה. זוהי לולאת ReAct-style שבה אחזור הוא כלי שהסוכן קורא לו."
    )

    story += [H2("שאלת סיכום", S)]
    story += qa_block(
        "אם היית צריך לפרוס מערכת זו לייצור מחר, מה הדבר הראשון שהיית משפר?",
        "הוספת cross-encoder לדירוג מחדש. האחזור הנוכחי עם bi-encoder מהיר "
        "אך עושה שגיאות אחזור שפוגעות באיכות התשובה — במיוחד לשאלות זמניות ושלילה "
        "שבהן הניסוח המדויק של הקטע שאוחזר חשוב. "
        "cross-encoder כגון ms-marco-MiniLM-L-6-v2 ידרג מחדש את 10 המועמדים הראשונים "
        "ויבטל את רוב כשלי האחזור בעלות זמן תגובה של ~0.5 שניות לשאילתה — "
        "פשרה מצוינת. עדיפות שנייה: LLM כשופט להחלפת הבדיקה הידנית של 10 תשובות "
        "ולקבלת מדדי איכות אמינים על 52 השאלות אוטומטית."
    )

    story += [SP(), HR(),
    Note("דוח זה נוצר מפרויקט RAG רפואת ילדים — כל ערכי המדדים משקפים "
         "הרצות צינור אמיתיות על קורפוס PDF אמיתי (הרצה 4: eval/run_eval.py, n=52; הרצה 8: ablation). "
         "Backend אינדקס: קבצי numpy .npy (ChromaDB הוחלף בשל תקלת persistence ב-Windows).", S)]

    return story


# ── Build PDF ─────────────────────────────────────────────────────────────────
def main():
    import os
    out_path = os.path.join(os.path.dirname(__file__), OUTPUT)

    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm,  bottomMargin=2*cm,
        title="צינור RAG רפואת ילדים — דוח מלא",
        author="מטלת RAG",
    )

    S = make_styles()
    story = build_content(S)
    doc.build(story)
    print("Report written to: report_he.pdf")


if __name__ == "__main__":
    main()
