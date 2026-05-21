# -*- coding: utf-8 -*-
"""
generate_presentation_en.py — English presenter guide: how to explain the RAG project to your instructor.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

pdfmetrics.registerFont(TTFont("Arial",        "C:/Windows/Fonts/arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold",   "C:/Windows/Fonts/arialbd.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Italic", "C:/Windows/Fonts/ariali.ttf"))

OUTPUT = "presentation_guide_en.pdf"

# ── Colours ───────────────────────────────────────────────────────────────────
NAVY     = HexColor("#1a3a5c")
BLUE     = HexColor("#2e6da4")
BLUE_LT  = HexColor("#d6e8f7")
TEAL     = HexColor("#0e7c7b")
TEAL_LT  = HexColor("#d0f0ef")
AMBER    = HexColor("#f4a400")
AMBER_LT = HexColor("#fff3cd")
GREEN    = HexColor("#1e7e34")
GREEN_LT = HexColor("#d4edda")
RED      = HexColor("#c0392b")
RED_LT   = HexColor("#fde8e7")
GREY_LT  = HexColor("#f5f5f5")
GREY_MID = HexColor("#cccccc")

# ── Styles ────────────────────────────────────────────────────────────────────
def make_styles():
    base = getSampleStyleSheet()

    def ps(name, **kw):
        defaults = dict(fontName="Arial", alignment=TA_LEFT, leading=14, fontSize=9)
        defaults.update(kw)
        return ParagraphStyle(name, parent=base["Normal"], **defaults)

    title_s  = ps("Title",  fontSize=24, fontName="Arial-Bold", textColor=white,
                  alignment=TA_CENTER, spaceAfter=0, leading=30)
    sub_s    = ps("Sub",    fontSize=13, textColor=BLUE_LT,
                  alignment=TA_CENTER, leading=18)
    h1       = ps("H1",     fontSize=15, fontName="Arial-Bold", textColor=NAVY,
                  spaceBefore=14, spaceAfter=5, leading=20)
    h2       = ps("H2",     fontSize=12, fontName="Arial-Bold", textColor=BLUE,
                  spaceBefore=10, spaceAfter=4, leading=16)
    h3       = ps("H3",     fontSize=10, fontName="Arial-Bold", textColor=NAVY,
                  spaceBefore=7,  spaceAfter=3, leading=14)
    body     = ps("Body",   fontSize=9,  leading=14, spaceAfter=3)
    bul      = ps("Bul",    fontSize=9,  leading=14, leftIndent=14, spaceAfter=2)
    note     = ps("Note",   fontSize=8,  fontName="Arial-Italic",
                  textColor=HexColor("#555555"))
    say      = ps("Say",    fontSize=9,  fontName="Arial-Italic", textColor=NAVY,
                  leading=14, spaceAfter=2)
    code     = ParagraphStyle("Code", parent=base["Normal"], fontName="Courier",
                              fontSize=7.5, leading=11, leftIndent=8,
                              backColor=GREY_LT, borderPadding=4, alignment=TA_LEFT)
    tip_txt  = ps("Tip",    fontSize=9, textColor=HexColor("#1a3a2a"), leading=13)
    warn_txt = ps("Warn",   fontSize=9, textColor=HexColor("#5a2000"), leading=13)
    num_lbl  = ps("Num",    fontSize=20, fontName="Arial-Bold", textColor=white,
                  alignment=TA_CENTER, leading=24)
    step_hdr = ps("StepH",  fontSize=11, fontName="Arial-Bold", textColor=NAVY,
                  leading=15)
    qa_q     = ps("QQ",     fontSize=9,  fontName="Arial-Bold", textColor=RED,
                  spaceBefore=6, spaceAfter=2)
    qa_a     = ps("QA",     fontSize=9,  textColor=HexColor("#1a3a5c"),
                  leftIndent=10, leading=14)
    time_s   = ps("Time",   fontSize=9,  fontName="Arial-Bold", textColor=TEAL,
                  alignment=TA_CENTER)

    return dict(title=title_s, sub=sub_s, h1=h1, h2=h2, h3=h3, body=body,
                bul=bul, note=note, say=say, code=code, tip=tip_txt,
                warn=warn_txt, num=num_lbl, step=step_hdr, qq=qa_q, qa=qa_a,
                time=time_s)


def SP(h=0.25): return Spacer(1, h * cm)
def HR(c=GREY_MID): return HRFlowable(width="100%", thickness=0.5, color=c)


# ── Building blocks ───────────────────────────────────────────────────────────

def colored_box(content_rows, bg, border=None, padding=8):
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
        style += [("BOX",       (0, 0), (-1, -1), 1.2, border),
                  ("LINEBEFORE",(0, 0), (0, -1),  4,   border)]
    t.setStyle(TableStyle(style))
    return t


def say_box(text, S):
    return colored_box(
        [Paragraph("Say:  " + text, S["say"])],
        bg=BLUE_LT, border=BLUE, padding=7
    )


def tip_box(title, text, S):
    return colored_box(
        [Paragraph("Tip  " + title, S["h3"]),
         Paragraph(text, S["tip"])],
        bg=GREEN_LT, border=GREEN, padding=7
    )


def warn_box(title, text, S):
    return colored_box(
        [Paragraph("Warning  " + title, S["h3"]),
         Paragraph(text, S["warn"])],
        bg=AMBER_LT, border=AMBER, padding=7
    )


def step_header(num, title, duration, S):
    num_cell = Table([[Paragraph(str(num), S["num"])]], colWidths=[1.0 * cm],
                     rowHeights=[1.0 * cm])
    num_cell.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))

    dur_cell = Table([[Paragraph(duration, S["time"])]], colWidths=[2.5 * cm],
                     rowHeights=[1.0 * cm])
    dur_cell.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), TEAL),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))

    title_cell = Table([[Paragraph(title, S["step"])]], colWidths=[12.8 * cm],
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
        Paragraph("Q:  " + q, S["qq"]),
        Paragraph(a, S["qa"]),
        SP(0.08),
    ]


def bullet(text, S):
    return Paragraph("•  " + text, S["bul"])


def make_table(data, col_widths, header_bg=BLUE):
    style = [
        ("BACKGROUND",    (0, 0), (-1,  0), header_bg),
        ("TEXTCOLOR",     (0, 0), (-1,  0), white),
        ("FONTNAME",      (0, 0), (-1,  0), "Arial-Bold"),
        ("FONTNAME",      (0, 1), (-1, -1), "Arial"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [white, GREY_LT]),
        ("GRID",          (0, 0), (-1, -1), 0.4, GREY_MID),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("ALIGN",         (0, 0), (-1, -1), "LEFT"),
    ]
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle(style))
    return t


# ── Cover ─────────────────────────────────────────────────────────────────────
def cover(S):
    cover_data = [[Paragraph("Project Presentation Guide", S["title"])]]
    ct = Table(cover_data, colWidths=[17 * cm])
    ct.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
        ("TOPPADDING",    (0, 0), (-1, -1), 32),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 32),
    ]))
    return [
        ct,
        SP(0.3),
        Paragraph("Pediatric RAG Pipeline — Build, Code, and Understanding", S["sub"]),
        SP(0.15),
        Paragraph("What to say  ·  How to explain  ·  What to demo  ·  Expected questions", S["sub"]),
        SP(0.5),
        HRFlowable(width="100%", thickness=1.5, color=BLUE),
        SP(0.3),
    ]


# ── Content ───────────────────────────────────────────────────────────────────
def build_content(S):
    story = []
    story += cover(S)

    # ── Presentation structure ────────────────────────────────────────────────
    story += [
        Paragraph("Recommended Presentation Structure — 20 Minutes", S["h1"]),
        SP(0.1),
    ]

    timeline_data = [
        ["Step", "Topic", "Time", "Goal"],
        ["1", "Opening — The Problem", "2 min",  "Hook the audience — 'Why RAG at all?'"],
        ["2", "Visual Architecture",   "3 min",  "Big picture before details"],
        ["3", "Code walkthrough — build_index", "4 min", "Demonstrate technical understanding"],
        ["4", "Code walkthrough — retrieval + generation", "3 min", "End-to-end data flow"],
        ["5", "Evaluation results + ablation", "4 min", "Real numbers + analysis"],
        ["6", "Lessons learned & improvements", "2 min", "Critical thinking depth"],
        ["7", "Q&A", "2 min", "Intellectual flexibility"],
    ]
    story += [
        make_table(timeline_data, [1.0*cm, 5.5*cm, 1.8*cm, 8.2*cm]),
        SP(),
    ]

    story += [
        tip_box("General advice",
                "Always open with WHY before WHAT. "
                "Your instructor wants to see that you understood the problem the technology solves, "
                "not just that you wrote code that runs.", S),
        SP(0.3),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 1
    # ══════════════════════════════════════════════════════════════════════════
    story += [step_header(1, "Opening — The Problem Being Solved", "2 min", S), SP(0.15)]

    story += [
        Paragraph("Open with:", S["h3"]),
        say_box(
            "My project builds a RAG system — Retrieval-Augmented Generation — "
            "that lets you ask clinical questions about pediatric medical textbooks "
            "and receive answers grounded in the source text, "
            "with an exact page-level citation.", S),
        SP(0.15),
        Paragraph("Then immediately explain: why isn't plain GPT/Claude enough?", S["h3"]),
        say_box(
            "A general language model doesn't know the specific cases in the AAP 2022 book — "
            "Simon, a child with febrile seizure, or a mother with rapid breathing. "
            "It will produce an answer that sounds correct but fabricates details. "
            "RAG forces every answer to come directly from retrieved text — "
            "a real line from the book — and cites the exact page.", S),
        SP(0.15),
        tip_box("Key moment",
                "Say this sentence: 'The simple test is to ask the same question to Claude "
                "without RAG — it produces a medically plausible answer that appears in no textbook.' "
                "This proves you understand when RAG is actually necessary.", S),
        SP(),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 2
    # ══════════════════════════════════════════════════════════════════════════
    story += [step_header(2, "Architecture — The Full Picture", "3 min", S), SP(0.15)]

    story += [
        Paragraph("Show the architecture diagram and walk through each stage in one line:", S["h3"]),
        SP(0.08),
    ]

    arch_rows = [
        ("PDF Files",
         "Two books — 1,096 pages after skipping image-only pages (fewer than 50 characters)."),
        ("Load + Clean",
         "PyMuPDF extracts text page-by-page. clean_text() removes PDF artifacts: "
         "page numbers, triple blank lines, lone bullet characters."),
        ("Chunking",
         "Two parallel strategies: fixed-size (400 chars, 50-char overlap) and "
         "paragraph-aware (100–700 chars at natural boundaries). "
         "Total: 10,107 + 5,250 chunks."),
        ("Embedding",
         "all-MiniLM-L6-v2 — 384-dimensional, L2-normalised. "
         "227 seconds on CPU for 10 K chunks. "
         "Normalisation turns cosine similarity into a dot product."),
        ("numpy index",
         ".npy + .json files. No external database. "
         "Originally ChromaDB — replaced due to a Windows bug that prevented "
         "persistence across processes."),
        ("Search + Generation",
         "scores = embeddings @ qvec.T  →  np.argpartition  →  top-5 chunks  "
         "→  prompt to claude-haiku-4-5  →  answer + [Source: ...] citation."),
    ]
    for label, desc in arch_rows:
        row = Table([[Paragraph(label, S["h3"]), Paragraph(desc, S["body"])]],
                    colWidths=[3.5*cm, 13*cm])
        row.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("LINEBELOW",     (0, 0), (-1, -1), 0.3, GREY_MID),
        ]))
        story += [row]

    story += [
        SP(0.2),
        warn_box("Common mistake",
                 "Don't say 'I used ChromaDB.' You did use ChromaDB but discovered a Windows bug "
                 "and migrated to numpy. That's exactly what an instructor wants to hear — "
                 "that you hit a real problem and thought through a solution.", S),
        SP(),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 3
    # ══════════════════════════════════════════════════════════════════════════
    story += [step_header(3, "Code Walkthrough — build_index.py", "4 min", S), SP(0.15)]

    story += [
        Paragraph("Open src/build_index.py and walk through the 4 main functions:", S["h3"]),
        SP(0.1),
    ]

    code_explain = [
        ("load_all_documents()",
         "Function in utils.py. PyMuPDF opens each PDF, extracts text page-by-page, "
         "runs clean_text(), builds a section_map from the TOC. "
         "Returns a list of {doc_id, text, metadata}."),
        ("chunk_fixed_size(docs, size=400, overlap=50)",
         "Sliding window. step = size - overlap = 350. "
         "Each step appends chunk[text[i : i+400]]. "
         "Tail < 30 chars is discarded."),
        ("embed_chunks(model, chunks, batch=128)",
         "model.encode(texts, normalize_embeddings=True). "
         "normalize=True applies L2 norm so cosine == dot product. "
         "Returns float32 array of shape (N, 384)."),
        ("save_index(chunks, embeddings, name)",
         "np.save(f'{name}_embeddings.npy', embeddings) + json.dump chunks to file. "
         "Load with np.load — zero external dependencies."),
    ]

    for func, desc in code_explain:
        story += [
            Paragraph(func, S["code"]),
            Paragraph(desc, S["body"]),
            SP(0.1),
        ]

    story += [
        say_box(
            "When you show embed_chunks, say: "
            "'Notice normalize_embeddings=True — that's why we can compute cosine similarity "
            "with a plain @ and don't need to divide by vector magnitudes. "
            "It's also what lets us store everything in a plain .npy file instead of a specialised database.'", S),
        SP(0.15),
        Paragraph("Code to know by heart:", S["h3"]),
        Paragraph(
            "vectors = model.encode(texts, batch_size=128, normalize_embeddings=True)\n"
            "np.save('fixed_embeddings.npy', vectors.astype(np.float32))",
            S["code"]),
        SP(),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 4
    # ══════════════════════════════════════════════════════════════════════════
    story += [step_header(4, "Code Walkthrough — retrieval.py + rag_system.py", "3 min", S), SP(0.15)]

    story += [
        Paragraph("Open src/retrieval.py — show the retrieve() function:", S["h3"]),
        Paragraph(
            "qvec   = model.encode([query], normalize_embeddings=True).astype(np.float32)\n"
            "scores = (embeddings @ qvec.T).flatten()         # (N,) cosine similarity\n"
            "top_idx = np.argpartition(scores, -k)[-k:]       # O(N), no full sort\n"
            "top_idx = top_idx[np.argsort(scores[top_idx])[::-1]]",
            S["code"]),
        SP(0.1),
        say_box(
            "This code performs a cosine search over 10,107 vectors in under a hundredth of a second. "
            "np.argpartition is O(N) — it doesn't sort everything, it just finds the top-k. "
            "We then sort only those k elements — much faster than argsort over the full array.", S),
        SP(0.15),
        Paragraph("Open src/rag_system.py — show the answer() function:", S["h3"]),
        Paragraph(
            "chunks   = retrieve(query, k=5, strategy='fixed')\n"
            "context  = '\\n'.join(c['text'] for c in chunks)\n"
            "prompt   = f'Context:\\n{context}\\n\\nQuestion: {query}'\n"
            "response = client.messages.create(model='claude-haiku-4-5-20251001',\n"
            "                                  max_tokens=512, messages=[...])",
            S["code"]),
        SP(0.1),
        say_box(
            "Notice the context is built from chunks sorted by descending score — "
            "the most relevant chunk is first. "
            "max_tokens=512 is enough for a clinical answer with citations "
            "and prevents long paragraph overflows from the context window.", S),
        SP(),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 5
    # ══════════════════════════════════════════════════════════════════════════
    story += [step_header(5, "Evaluation Results and Ablation Study", "4 min", S), SP(0.15)]

    story += [
        Paragraph("Show the tables from the report and explain every number:", S["h3"]),
        SP(0.08),
    ]

    results_data = [
        ["Metric", "Value", "How to explain it aloud"],
        ["Hit@5 = 0.827",
         "43 / 52 questions",
         "'In almost 83% of questions, the text containing the answer appears in the top-5 chunks returned by the system.'"],
        ["Precision@5 = 0.881",
         "4.4 out of 5",
         "'Nearly every retrieved chunk is relevant — very little noise. This is higher than expected because the corpus is focused.'"],
        ["Latency = 3.14 s",
         "CPU only",
         "'Time breaks down as: ~0.1 s numpy retrieval, ~3 s Claude API generation. The bottleneck is the LLM, not retrieval.'"],
        ["Negation = 1.000",
         "8/8 — perfect",
         "'A surprise — we expected this to be the hardest category. The system prompt rules worked well for absence confirmation.'"],
        ["Factual = 0.792",
         "19/24 — weakest",
         "'5 failures — mostly Kliegman decision-tree terms that fixed-size chunking split at the wrong boundary.'"],
    ]
    story += [
        make_table(results_data, [3.5*cm, 2.5*cm, 10*cm]),
        SP(0.2),
        Paragraph("Ablation — this is where you show deep understanding:", S["h3"]),
        SP(0.08),
    ]

    abl_data = [
        ["Experiment", "Hit@k", "Precision@k", "What to say aloud"],
        ["fixed  k=5  (baseline)", "0.900", "0.810",
         "'Baseline on the first 20 questions.'"],
        ["paragraph  k=5",         "0.900", "0.870",
         "'Same hit rate — but 6% higher precision. Paragraph chunks are more on-target.'"],
        ["fixed  k=3",             "0.850", "0.850",
         "'Precision rises because there is less noise — but we lose one hit on a numerical question.'"],
        ["fixed  k=8",             "0.900", "0.787",
         "'Hit does not improve beyond k=5 — we only add noise chunks. k=5 is the sweet spot.'"],
    ]
    story += [
        make_table(abl_data, [3.5*cm, 1.8*cm, 2.5*cm, 8.7*cm]),
        SP(0.2),
        say_box(
            "Frame the ablation like this: 'I ran 4 experiments to isolate what actually matters. "
            "The surprising finding: chunking strategy matters more than k. "
            "Paragraph chunking gives 6% higher precision at zero additional latency cost. "
            "k=8 doesn't help because it introduces low-relevance chunks that confuse the model.'", S),
        SP(),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 6
    # ══════════════════════════════════════════════════════════════════════════
    story += [step_header(6, "Lessons Learned — What I Would Improve", "2 min", S), SP(0.15)]

    story += [
        Paragraph(
            "This is the step that separates 'I used a library' from 'I understood the material':", S["body"]),
        SP(0.1),
    ]

    improvements = [
        ("Cross-encoder re-ranking",
         "A bi-encoder is fast but less precise — it encodes the query and chunk independently. "
         "A cross-encoder sees both together and is significantly more accurate. "
         "I would add ms-marco-MiniLM to re-rank the top-10 results — "
         "cost ~0.5 s, worthwhile for temporal and multi-hop questions."),
        ("Sentence-boundary overlap",
         "The current 50-char overlap cuts at an arbitrary position mid-sentence. "
         "I would compute sentence boundaries first and ensure every chunk starts and ends on a complete sentence. "
         "This would improve the 'numerical' category where digits get split across chunks."),
        ("LLM-as-Judge evaluation",
         "Manual quality assessment of 10 questions is not enough. "
         "I would use Claude Sonnet to verify whether each generated answer is "
         "actually supported by its cited passage — "
         "a faithfulness check that scales to all 52 questions automatically."),
    ]

    for title, desc in improvements:
        row = Table([[Paragraph(title, S["h3"]), Paragraph(desc, S["body"])]],
                    colWidths=[4*cm, 12.5*cm])
        row.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("LINEBELOW",     (0, 0), (-1, -1), 0.3, GREY_MID),
        ]))
        story.append(row)

    story += [
        SP(0.2),
        tip_box("Closing sentence",
                "Finish with: 'The most important thing I learned is that the technical pipeline is "
                "relatively straightforward — the real challenge is diagnosing where the failures are "
                "and deciding what to improve first. Ablation analysis is the tool for that.'", S),
        SP(),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # Expected Q&A
    # ══════════════════════════════════════════════════════════════════════════
    story += [PageBreak()]
    story += [
        Paragraph("Expected Instructor Questions — and Answers", S["h1"]),
        SP(0.1),
        Paragraph(
            "Read through this several times before presenting — "
            "these are the questions that separate a 90 from a 100.", S["note"]),
        SP(0.2),
    ]

    # Category: Conceptual
    story += [Paragraph("Conceptual Understanding", S["h2"]), HR(BLUE), SP(0.1)]
    for q, a in [
        ("What is the difference between RAG and fine-tuning?",
         "Fine-tuning forgets — it 'colours' the model weights with new data "
         "but can overwrite existing knowledge (catastrophic forgetting). "
         "RAG never touches the weights — it injects external context at inference time. "
         "RAG is also more up-to-date: you can swap the documents without retraining. "
         "Fine-tuning is best for style and fixed tasks; RAG is best for factual knowledge that changes."),
        ("Why a bi-encoder and not a cross-encoder for retrieval?",
         "A cross-encoder is more accurate but O(N) — it needs a forward pass for every (query, document) pair. "
         "For an index of 10 K chunks that means 10,000 model calls per question — roughly 30 s on CPU. "
         "A bi-encoder computes the query embedding once (384-dim) and then does a matrix multiply — "
         "O(1) given a prebuilt index. "
         "Strategy: bi-encoder for retrieval, cross-encoder for re-ranking if needed."),
        ("Why L2 normalisation?",
         "Without normalisation, the dot product depends on vector magnitude — longer sentences score higher "
         "simply because they contain more words. "
         "Normalisation makes the metric angle-only (semantic direction) "
         "and enables fair comparison between a two-word decision-tree fragment and a long paragraph."),
        ("What is Hit@k versus Precision@k?",
         "Hit@k: binary per question — 1 if at least one correct chunk appears in the top-k, 0 otherwise. "
         "Precision@k: averaged fraction — how many of the k retrieved chunks are relevant? "
         "Hit@k measures recall (did we find it?). Precision@k measures accuracy (how much noise?). "
         "The goal is to maximise Hit while keeping Precision high — k=5 is the balance point."),
    ]:
        story += qa_pair(q, a, S)

    story += [SP(0.1), Paragraph("The RAG Pipeline", S["h2"]), HR(BLUE), SP(0.1)]
    for q, a in [
        ("What happens if the correct chunk is not retrieved?",
         "The system answers based only on whatever was retrieved. "
         "If no relevant chunk is found, the system prompt tells Claude to say "
         "'The information was not found in the provided sources.' "
         "Known failure mode: occasionally the model still cites the closest chunk as a fallback — "
         "this was noted in the failure analysis."),
        ("Why chunk size 400 and not 200 or 800?",
         "200: too small — a sentence fragment. The embedding receives little context and retrieval noise grows. "
         "800: too large — two unrelated clinical points merge into one chunk, diluting the semantic signal. "
         "400 ≈ 80 tokens — about 2 sentences, a coherent context, a distinctive score. "
         "Validated by ablation: changing k had little effect, but chunking strategy did."),
        ("What is the difference between dense retrieval and BM25?",
         "BM25 retrieves by keyword matching (a TF-IDF variant) — if the keyword isn't in the text, "
         "the chunk won't be returned. "
         "Dense retrieval searches by meaning — 'febrile seizure discharge' can surface a page "
         "that writes 'criteria for an afebrile child.' "
         "Dense is better for natural language; BM25 is better for unique scientific names (drug names)."),
    ]:
        story += qa_pair(q, a, S)

    story += [SP(0.1), Paragraph("Technical Questions", S["h2"]), HR(BLUE), SP(0.1)]
    for q, a in [
        ("Why did you replace ChromaDB with numpy?",
         "ChromaDB 1.5.9 has an HNSW-specific bug on Windows: the Rust index loads into memory "
         "during the build process but is not written to disk correctly. "
         "Every new Python process that opened the same path got an InternalError. "
         "A sleep+verify workaround worked within one process but failed across processes. "
         "numpy is sufficient for 10 K vectors, fully portable, and has zero additional dependencies."),
        ("np.argpartition vs np.argsort — what is the difference?",
         "np.argsort sorts all N=10,107 elements — O(N log N). "
         "np.argpartition finds the k largest in O(N) without a full sort. "
         "We then sort only those k=5 elements — O(k log k) which is effectively constant. "
         "In practice the difference is small at N=10 K, but it is the conceptually correct approach."),
        ("Why is query embedding done inside retrieve() rather than in rag_system.py?",
         "Separation of concerns: retrieval.py owns everything related to the index. "
         "rag_system.py is a pure orchestrator — it knows nothing about vectors. "
         "This also allows retrieve() to be tested independently without an LLM."),
        ("What is semantic drift?",
         "When chunks are too large, the model's attention 'spreads' across the full text "
         "and may answer a nearby but different question. "
         "Example: a question about otitis media receives an answer about chronic ear disease "
         "because both appear in the same oversized chunk."),
    ]:
        story += qa_pair(q, a, S)

    story += [SP(0.1), Paragraph("What-If Questions", S["h2"]), HR(BLUE), SP(0.1)]
    for q, a in [
        ("What if the corpus grew to one million documents?",
         "A numpy flat file is sufficient for ~100 K vectors in memory. "
         "For one million: migrate to FAISS (approximate nearest neighbour, GPU) "
         "or Qdrant/Weaviate (distributed). "
         "Also shard by medical domain — a question about a sick child doesn't need to search oncology. "
         "The retrieval interface doesn't change — only the backend."),
        ("What if a document is updated every day?",
         "Incremental indexing: each document has a hash. "
         "When the hash changes — re-chunk and re-embed only that document, "
         "replace the relevant rows in .npy and .json. "
         "At higher scale: a database with upsert-by-ID such as Qdrant."),
        ("What if someone asks a question unrelated to pediatric medicine?",
         "The system returns the 5 closest chunks from the corpus — "
         "a cooking question would receive unrelated medical passages. "
         "The system prompt tells Claude to answer 'not found' when the context is not relevant. "
         "Improvement: add a domain classifier as a first stage to check whether the question is in scope."),
    ]:
        story += qa_pair(q, a, S)

    # ══════════════════════════════════════════════════════════════════════════
    # Quick-reference glossary
    # ══════════════════════════════════════════════════════════════════════════
    story += [PageBreak()]
    story += [
        Paragraph("Quick-Reference Glossary — Terms You Must Get Right", S["h1"]),
        SP(0.1),
    ]

    terms_data = [
        ["Term", "Correct definition to say aloud", "Common mistake to avoid"],
        ["RAG",
         "Injecting externally retrieved context into an LLM prompt, forcing the answer to be grounded in specific documents.",
         "'It's just search' — it is search plus grounded generation."],
        ["Embedding",
         "A vector representation of text in R^384 such that semantically similar sentences are close in cosine distance.",
         "'Measuring distance' — it measures angle (cosine), not Euclidean distance."],
        ["Chunking",
         "Splitting a document into pieces sized to enable accurate embedding and focused retrieval.",
         "'Splitting into paragraphs' — it is a strategy you choose, not just paragraph breaks."],
        ["Hit@k",
         "Binary metric per question: 1 if at least one correct chunk appears in the top-k results, 0 otherwise.",
         "Don't confuse with Precision — Hit measures recall, not accuracy."],
        ["Precision@k",
         "What fraction of the k retrieved chunks are relevant? Averaged across all questions.",
         "Not 'how many answers are correct' — it measures the chunks, not the final answer."],
        ["Bi-encoder",
         "A model that encodes query and document independently into vectors, enabling pre-computation.",
         "Don't confuse with cross-encoder, which sees query + document together."],
        ["L2 Normalisation",
         "Dividing a vector by its norm so ||v||=1. After this, cosine similarity equals dot product.",
         "Don't say 'normalisation' without explaining why — the answer: so we can use @."],
        ["Ablation Study",
         "An experiment that changes one parameter at a time to isolate its effect on performance.",
         "Not 'tests' — an ablation is a systematic experiment, not debugging."],
    ]
    story += [
        make_table(terms_data, [2.5*cm, 7.5*cm, 6.5*cm]),
        SP(),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # Do / Don't
    # ══════════════════════════════════════════════════════════════════════════
    story += [
        Paragraph("Do and Don't During the Presentation", S["h1"]),
        SP(0.1),
    ]

    do_data = [
        ["DO", "DON'T"],
        ["Talk about the ChromaDB bug — it shows you hit a real problem",
         "Say 'everything worked smoothly' — an instructor won't believe it"],
        ["Frame the ablation as a systematic experiment with a hypothesis",
         "Say 'I just tried a few values'"],
        ["Show real code in the terminal — not only slides",
         "Rely solely on the PDF — this is a code demonstration"],
        ["Say 'I didn't know' and then explain what you learned",
         "Invent an answer to something you don't know — instructors notice"],
        ["Name the tradeoff in every decision (why k=5 and not k=3)",
         "Say 'I chose X because X works' — there is always something to lose"],
        ["Run one live query: python -c \"from src.rag_system import answer; ...\"",
         "Skip the live demo — it is the strongest moment of the presentation"],
    ]
    story += [
        make_table(do_data, [8.25*cm, 8.25*cm], header_bg=NAVY),
        SP(),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # Live demo script
    # ══════════════════════════════════════════════════════════════════════════
    story += [
        Paragraph("Live Demo Script — Run This Before the Presentation", S["h1"]),
        SP(0.1),
        Paragraph("Command to run in the terminal from the project directory:", S["body"]),
        Paragraph(
            "# Run a single question\n"
            "python -c \"\n"
            "from src.rag_system import answer\n"
            "import json\n"
            "r = answer('What are the discharge criteria for febrile seizure?')\n"
            "print(r['answer'])\n"
            "print('Sources:', r['sources'])\n"
            "\"",
            S["code"]),
        SP(0.1),
        Paragraph("Run the full evaluation (results saved to eval_run.log):", S["body"]),
        Paragraph("python eval/run_eval.py --strategy fixed --k 5", S["code"]),
        SP(0.1),
        Paragraph("Run the ablation study:", S["body"]),
        Paragraph("python eval/run_eval.py --ablation", S["code"]),
        SP(0.1),
        tip_box("Practice exercise",
                "Run one question live and explain every output line: "
                "what chunk_id means, what the score represents, and why the answer "
                "cites exactly those sources. "
                "If there is an error — that is fine, say: "
                "'Interesting error, let's understand it together.'", S),
        SP(),
        HR(NAVY),
        SP(0.2),
        Paragraph(
            "Good luck! — The project is solid, the numbers are real, and the code works. "
            "All that remains is to explain it with confidence.",
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
        title="Project Presentation Guide",
        author="RAG Assignment",
    )
    S = make_styles()
    story = build_content(S)
    doc.build(story)
    print("Presentation guide written to: presentation_guide_en.pdf")


if __name__ == "__main__":
    main()
