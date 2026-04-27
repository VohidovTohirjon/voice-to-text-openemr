"""
Generate CSC436_Team1_FinalPresentation.pptx
Run: python make_presentation.py
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
import copy

# ── Palette ─────────────────────────────────────────────────────────────────
NAVY   = RGBColor(0x0F, 0x17, 0x2A)   # slide background
TEAL   = RGBColor(0x0F, 0x76, 0x6E)   # accent / headings
BLUE   = RGBColor(0x1D, 0x4E, 0xD8)   # secondary accent
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
SLATE  = RGBColor(0xCB, 0xD5, 0xE1)   # body text
GREEN  = RGBColor(0x22, 0xC5, 0x5E)   # pass / highlight
ORANGE = RGBColor(0xF9, 0x73, 0x16)   # warning / challenge

# ── Slide dimensions (16:9 widescreen) ──────────────────────────────────────
W = Inches(13.33)
H = Inches(7.5)

prs = Presentation()
prs.slide_width  = W
prs.slide_height = H

BLANK = prs.slide_layouts[6]   # completely blank layout


# ── Helpers ──────────────────────────────────────────────────────────────────

def new_slide():
    slide = prs.slides.add_slide(BLANK)
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = NAVY
    return slide


def add_rect(slide, l, t, w, h, color):
    shape = slide.shapes.add_shape(1, l, t, w, h)  # MSO_SHAPE_TYPE.RECTANGLE = 1
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    return shape


def add_text(slide, text, l, t, w, h,
             size=24, bold=False, color=WHITE, align=PP_ALIGN.LEFT,
             wrap=True):
    txb = slide.shapes.add_textbox(l, t, w, h)
    txb.word_wrap = wrap
    tf = txb.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return txb


def add_para(tf, text, size=20, bold=False, color=WHITE, align=PP_ALIGN.LEFT, space_before=6):
    from pptx.util import Pt
    p = tf.add_paragraph()
    p.alignment = align
    p.space_before = Pt(space_before)
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return p


def slide_header(slide, title, subtitle=None, accent=TEAL):
    """Dark header bar with title."""
    add_rect(slide, Inches(0), Inches(0), W, Inches(1.35), accent)
    add_text(slide, title,
             Inches(0.35), Inches(0.12), W - Inches(0.7), Inches(0.9),
             size=34, bold=True, color=WHITE)
    if subtitle:
        add_text(slide, subtitle,
                 Inches(0.35), Inches(0.92), W - Inches(0.7), Inches(0.38),
                 size=16, bold=False, color=RGBColor(0xE2, 0xE8, 0xF0))


def bullet_box(slide, items, l, t, w, h,
                title=None, title_color=TEAL, bullet="•",
                size=19, title_size=22):
    """A text box with optional title and bulleted items."""
    txb = slide.shapes.add_textbox(l, t, w, h)
    txb.word_wrap = True
    tf = txb.text_frame
    tf.word_wrap = True
    first = True
    if title:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(title_size)
        run.font.bold = True
        run.font.color.rgb = title_color
    for item in items:
        p = tf.paragraphs[0] if (first and not title) else tf.add_paragraph()
        first = False
        p.alignment = PP_ALIGN.LEFT
        p.space_before = Pt(4)
        run = p.add_run()
        run.text = f"{bullet}  {item}"
        run.font.size = Pt(size)
        run.font.color.rgb = WHITE
    return txb


# ============================================================================
# SLIDE 1 — Title
# ============================================================================
slide = new_slide()

# Gradient-like accent bar
add_rect(slide, Inches(0), Inches(2.6), W, Inches(2.4), BLUE)
add_rect(slide, Inches(0), Inches(2.6), W, Inches(2.4), TEAL)

# Title
add_text(slide, "Voice-to-Text for OpenEMR",
         Inches(0.5), Inches(2.75), W - Inches(1), Inches(1.2),
         size=44, bold=True, color=WHITE, align=PP_ALIGN.CENTER)

# Subtitle
add_text(slide, "CSC 436  ·  Spring 2026  ·  University of Arizona",
         Inches(0.5), Inches(3.85), W - Inches(1), Inches(0.6),
         size=20, color=RGBColor(0xE2, 0xE8, 0xF0), align=PP_ALIGN.CENTER)

# Team
add_text(slide, "Andy Siegel  ·  Fig Lesser  ·  Kianny Calvo  ·  Tokhirjon Vokhidov",
         Inches(0.5), Inches(4.4), W - Inches(1), Inches(0.5),
         size=18, color=SLATE, align=PP_ALIGN.CENTER)

# Bottom bar
add_rect(slide, Inches(0), H - Inches(0.45), W, Inches(0.45), NAVY)
add_text(slide, "Team 1",
         Inches(0.5), H - Inches(0.42), Inches(3), Inches(0.38),
         size=13, color=SLATE)


# ============================================================================
# SLIDE 2 — Problem
# ============================================================================
slide = new_slide()
slide_header(slide, "The Problem", accent=BLUE)

add_text(slide,
         "Clinicians spend 30–50 % of their workday on EHR documentation",
         Inches(0.5), Inches(1.55), W - Inches(1), Inches(0.7),
         size=26, bold=True, color=WHITE)

items = [
    "OpenEMR — a widely-used open-source EHR — has no native voice input",
    "Typing notes during a patient encounter breaks eye contact and disrupts the visit",
    "Documentation overload is a leading driver of physician burnout",
    "Existing commercial voice tools are expensive, cloud-dependent, or not integrated with OpenEMR",
]
bullet_box(slide, items,
           Inches(0.5), Inches(2.35), W - Inches(1), Inches(4.0),
           size=21)

# Accent quote
add_rect(slide, Inches(0.5), Inches(5.95), Inches(0.08), Inches(0.9), TEAL)
add_text(slide,
         '"The most time-consuming part of the encounter workflow is dictating the chief complaint."'
         "\n— Nirav Merchant, Co-PI NSF CyVerse (stakeholder interview)",
         Inches(0.75), Inches(5.9), W - Inches(1.2), Inches(1.0),
         size=15, color=SLATE)


# ============================================================================
# SLIDE 3 — Solution
# ============================================================================
slide = new_slide()
slide_header(slide, "The Solution", accent=TEAL)

# Pipeline boxes
steps = [
    ("🎙  Speak", "Clinician speaks during the encounter"),
    ("⚡  Transcribe", "Whisper runs locally — no cloud"),
    ("🧠  Extract", "spaCy NLP identifies clinical entities"),
    ("✅  Confirm", "Clinician reviews & approves"),
    ("📋  Insert", "Text injected into OpenEMR form"),
]
box_w = Inches(2.3)
gap   = Inches(0.18)
start_x = Inches(0.35)
for i, (label, desc) in enumerate(steps):
    x = start_x + i * (box_w + gap)
    add_rect(slide, x, Inches(1.6), box_w, Inches(1.55),
             TEAL if i % 2 == 0 else BLUE)
    add_text(slide, label,
             x + Inches(0.1), Inches(1.65), box_w - Inches(0.2), Inches(0.55),
             size=17, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(slide, desc,
             x + Inches(0.1), Inches(2.2), box_w - Inches(0.2), Inches(0.85),
             size=13, color=SLATE, align=PP_ALIGN.CENTER)

# Arrows between boxes
for i in range(4):
    ax = start_x + (i + 1) * (box_w + gap) - gap + Inches(0.01)
    add_text(slide, "›",
             ax - Inches(0.12), Inches(1.8), Inches(0.3), Inches(0.5),
             size=26, bold=True, color=WHITE, align=PP_ALIGN.CENTER)

# Key points
bullet_box(slide, [
    "Chrome extension — attaches to the OpenEMR encounter page, no source-code changes required",
    "All processing is local — no audio or patient data ever leaves the machine (HIPAA-aligned)",
    "Confirm-before-fill safeguard — clinician reviews the transcript before anything is written to the EHR",
    "Dual NLP: fast spaCy rule-based path + optional local Ollama LLM for conversational phrasing",
],
Inches(0.5), Inches(3.4), W - Inches(1), Inches(3.4), size=19)


# ============================================================================
# SLIDE 4 — Goals / Success Criteria
# ============================================================================
slide = new_slide()
slide_header(slide, "Project Goal & Success Criteria", accent=BLUE)

criteria = [
    ("Word Error Rate (WER)", "< 10 % on a standardized clinical speech test set",
     "Measured against publicly available medical ASR benchmarks (MedASR, MedWhisper)"),
    ("Medical Terminology Accuracy", "> 90 % on drug names, diagnoses, procedures",
     "Evaluated against curated set from UMLS clinical terminology sources"),
    ("Transcription Latency", "≤ 2 seconds from end of utterance to text display",
     "Timed end-to-end: stop button → text appears in preview panel"),
    ("Offline Operation", "Within 5 % of online accuracy and latency baseline",
     "System runs fully without internet; comparison measured in controlled setting"),
]

row_h = Inches(1.2)
y0 = Inches(1.5)
for i, (metric, target, method) in enumerate(criteria):
    y = y0 + i * row_h
    color = TEAL if i % 2 == 0 else BLUE
    add_rect(slide, Inches(0.35), y, Inches(0.06), row_h - Inches(0.08), color)
    add_text(slide, metric,
             Inches(0.55), y + Inches(0.05), Inches(4.5), Inches(0.45),
             size=19, bold=True, color=color)
    add_text(slide, target,
             Inches(0.55), y + Inches(0.42), Inches(4.5), Inches(0.38),
             size=22, bold=True, color=GREEN)
    add_text(slide, method,
             Inches(5.3), y + Inches(0.15), Inches(7.5), Inches(0.85),
             size=15, color=SLATE)


# ============================================================================
# SLIDE 5 — Project Users
# ============================================================================
slide = new_slide()
slide_header(slide, "Project Users", accent=TEAL)

# Left column — primary users
bullet_box(slide, [
    "Primary care physicians",
    "Urgent care clinicians",
    "Outpatient specialists",
    "Any provider using OpenEMR for encounter documentation",
],
Inches(0.5), Inches(1.6), Inches(5.8), Inches(3.2),
title="Who Uses This?", size=19)

add_text(slide, "Why?",
         Inches(0.5), Inches(4.7), Inches(5.8), Inches(0.45),
         size=20, bold=True, color=TEAL)
bullet_box(slide, [
    "Reduce documentation time — speak instead of type",
    "Keep attention on the patient during the encounter",
    "Lower risk of burnout from after-hours charting",
],
Inches(0.5), Inches(5.1), Inches(5.8), Inches(2.1), size=17)

# Right column — stakeholder card
add_rect(slide, Inches(6.7), Inches(1.6), Inches(6.1), Inches(5.6),
         RGBColor(0x1E, 0x29, 0x3B))
add_text(slide, "Stakeholder",
         Inches(6.9), Inches(1.7), Inches(5.7), Inches(0.45),
         size=13, color=TEAL, bold=True)
add_text(slide, "Nirav Merchant",
         Inches(6.9), Inches(2.1), Inches(5.7), Inches(0.6),
         size=26, bold=True, color=WHITE)
add_text(slide, "Co-PI, NSF CyVerse",
         Inches(6.9), Inches(2.65), Inches(5.7), Inches(0.4),
         size=16, color=SLATE)

feedback = [
    "✓  Validated 'Reason for Visit' as the highest-priority insertion target",
    "✓  Confirmed: dictating the chief complaint is the most time-consuming step",
    "✓  Requested confirm-before-fill to prevent accidental EHR writes",
    "✓  Positively called out the safety dialog in follow-up feedback",
]
for j, f in enumerate(feedback):
    add_text(slide, f,
             Inches(6.9), Inches(3.25) + j * Inches(0.65),
             Inches(5.7), Inches(0.6),
             size=15, color=WHITE)


# ============================================================================
# SLIDE 6 — What's Novel
# ============================================================================
slide = new_slide()
slide_header(slide, "What's Novel?", accent=BLUE)

# Comparison table
headers = ["Existing Option", "Problem"]
rows = [
    ["Nuance Dragon Medical",     "$$$, cloud-required, not OpenEMR-integrated"],
    ["Google/Browser Speech API", "No medical accuracy, sends PHI to the cloud"],
    ["EHR-vendor voice tools",    "Tied to expensive proprietary EHR platforms"],
    ["Generic open-source STT",   "No clinical NLP, no OpenEMR integration"],
]

table_l, table_t = Inches(0.4), Inches(1.55)
table_w, table_h = Inches(6.0), Inches(3.4)
col_ws = [Inches(2.5), Inches(3.45)]

# Header row
add_rect(slide, table_l, table_t, table_w, Inches(0.45), TEAL)
for ci, (hdr, cw) in enumerate(zip(headers, col_ws)):
    x = table_l + sum(col_ws[:ci])
    add_text(slide, hdr, x + Inches(0.08), table_t + Inches(0.05),
             cw - Inches(0.1), Inches(0.38),
             size=15, bold=True, color=WHITE)

for ri, row in enumerate(rows):
    y = table_t + Inches(0.45) + ri * Inches(0.73)
    bg = RGBColor(0x1E, 0x29, 0x3B) if ri % 2 == 0 else RGBColor(0x0F, 0x17, 0x2A)
    add_rect(slide, table_l, y, table_w, Inches(0.73), bg)
    for ci, (cell, cw) in enumerate(zip(row, col_ws)):
        x = table_l + sum(col_ws[:ci])
        add_text(slide, cell, x + Inches(0.08), y + Inches(0.08),
                 cw - Inches(0.1), Inches(0.6),
                 size=14, color=WHITE if ci == 0 else SLATE)

# Right column — what we do
add_rect(slide, Inches(6.7), Inches(1.55), Inches(6.1), Inches(5.65),
         RGBColor(0x0C, 0x38, 0x27))
add_text(slide, "Our Approach",
         Inches(6.9), Inches(1.65), Inches(5.7), Inches(0.5),
         size=21, bold=True, color=GREEN)

our = [
    "Free & open-source — zero licensing cost",
    "Fully offline — no PHI leaves the machine",
    "Browser extension — no OpenEMR source changes, survives EHR updates",
    "Medical-domain NLP — chief complaint, assessment, plan, meds, diagnoses",
    "Dual NLP engine — fast spaCy + local Ollama LLM with graceful fallback",
    "Confirm-before-fill — patient safety built into the UX",
]
for j, item in enumerate(our):
    add_text(slide, f"✓  {item}",
             Inches(6.9), Inches(2.3) + j * Inches(0.55),
             Inches(5.7), Inches(0.52),
             size=15, color=WHITE)

# Summary sentence
add_text(slide,
         "There is no existing free, offline, OpenEMR-native voice-to-text tool with medical-domain NLP.",
         Inches(0.4), Inches(5.2), Inches(6.1), Inches(0.9),
         size=16, bold=True, color=GREEN)


# ============================================================================
# SLIDE 7 — System Architecture
# ============================================================================
slide = new_slide()
slide_header(slide, "System Architecture", accent=TEAL)

# Three component boxes
components = [
    ("Chrome Extension\n(Manifest V3)",
     "content.js · scanner.js\nFloating panel UI\nField detection & injection",
     BLUE),
    ("FastAPI ASR Service\nlocalhost:8000",
     "/transcribe  (Whisper base)\n/extract  (spaCy + Ollama)\n/transcribe_and_extract",
     TEAL),
    ("OpenEMR\n(Docker · localhost:80)",
     "Encounter form\ntextarea[name=\"reason\"]\nReason for Visit field",
     RGBColor(0x44, 0x25, 0x9B)),
]

comp_w = Inches(3.5)
comp_h = Inches(2.6)
gap_c  = Inches(0.8)
y_c    = Inches(1.7)
starts = [Inches(0.4), Inches(4.9), Inches(9.4)]

for (label, detail, color), x in zip(components, starts):
    add_rect(slide, x, y_c, comp_w, comp_h, color)
    add_text(slide, label,
             x + Inches(0.15), y_c + Inches(0.12),
             comp_w - Inches(0.3), Inches(0.75),
             size=17, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(slide, detail,
             x + Inches(0.15), y_c + Inches(0.88),
             comp_w - Inches(0.3), Inches(1.6),
             size=13, color=SLATE, align=PP_ALIGN.CENTER)

# Arrows
for x in [starts[0] + comp_w, starts[1] + comp_w]:
    add_text(slide, "⟷",
             x + Inches(0.15), y_c + Inches(0.9),
             gap_c - Inches(0.3), Inches(0.8),
             size=28, bold=True, color=WHITE, align=PP_ALIGN.CENTER)

# Labels under arrows
add_text(slide, "POST audio / JSON transcript",
         starts[0] + comp_w + Inches(0.05), y_c + Inches(1.7),
         gap_c + Inches(0.2), Inches(0.5),
         size=11, color=SLATE, align=PP_ALIGN.CENTER)
add_text(slide, "DOM injection\n(no HTTP)",
         starts[1] + comp_w + Inches(0.05), y_c + Inches(1.7),
         gap_c + Inches(0.2), Inches(0.5),
         size=11, color=SLATE, align=PP_ALIGN.CENTER)

# Key decisions
add_rect(slide, Inches(0.4), Inches(4.55), W - Inches(0.8), Inches(0.08), TEAL)
decisions = [
    "Local Whisper — privacy + offline",
    "FastAPI — browser-callable, model-swappable",
    "Extension over PHP edits — no OpenEMR source changes",
    "CORS middleware — extension ↔ API",
    "Confirm-before-fill — patient safety UX",
]
add_text(slide, "Key Decisions:  " + "   ·   ".join(decisions),
         Inches(0.4), Inches(4.7), W - Inches(0.8), Inches(0.6),
         size=13, color=SLATE)

# HIPAA note
add_text(slide, "⚠  All audio and text stays on the provider's machine — no network egress",
         Inches(0.4), Inches(5.45), W - Inches(0.8), Inches(0.5),
         size=15, bold=True, color=GREEN)


# ============================================================================
# Helper: acceptance-test slide
# ============================================================================
def at_slide(num, title, steps_list, pass_criteria, accent=TEAL):
    slide = new_slide()
    slide_header(slide, f"AT{num} — {title}",
                 subtitle=f"Acceptance Test {num} of 5", accent=accent)

    # Steps
    add_text(slide, "What we show:",
             Inches(0.5), Inches(1.6), Inches(6.5), Inches(0.45),
             size=18, bold=True, color=accent)
    for i, s in enumerate(steps_list):
        add_text(slide, f"{i+1}.  {s}",
                 Inches(0.65), Inches(2.05) + i * Inches(0.62),
                 Inches(6.3), Inches(0.58),
                 size=17, color=WHITE)

    # Pass criteria box
    add_rect(slide, Inches(7.2), Inches(1.6), Inches(5.7), Inches(0.45),
             GREEN)
    add_text(slide, "PASS criteria",
             Inches(7.3), Inches(1.65), Inches(5.5), Inches(0.38),
             size=15, bold=True, color=NAVY)

    add_rect(slide, Inches(7.2), Inches(2.05), Inches(5.7),
             Inches(0.08) + len(pass_criteria) * Inches(0.68),
             RGBColor(0x0C, 0x38, 0x27))
    for i, p in enumerate(pass_criteria):
        add_text(slide, f"✓  {p}",
                 Inches(7.35), Inches(2.12) + i * Inches(0.68),
                 Inches(5.4), Inches(0.65),
                 size=15, color=WHITE)

    return slide


# ============================================================================
# SLIDE 8 — AT1: Field Detection
# ============================================================================
at_slide(
    1, "Field Detection",
    [
        "Open OpenEMR encounter page in Chrome with extension loaded",
        "Observe: extension panel appears, attached to the right of the page",
        "Observe: 'Reason for Visit' textarea is highlighted in green",
        "Navigate to login page — panel does NOT appear",
    ],
    [
        "Panel appears only on encounter / new-patient pages",
        "Correct field (textarea[name=\"reason\"]) is identified and highlighted",
        "Panel stays hidden on the login page",
    ],
    accent=TEAL,
)

# ============================================================================
# SLIDE 9 — AT2: Transcript Preview + Edit
# ============================================================================
at_slide(
    2, "Transcript Preview & Edit",
    [
        "Click 'Use demo text' in the extension panel",
        "Observe: 'Patient reports headache and mild fever for two days.' appears",
        "Edit the preview text directly in the panel",
        "Observe: edits persist in the preview before any form interaction",
    ],
    [
        "Demo transcript loads instantly into the preview textarea",
        "Preview text is fully editable by the clinician",
        "No text has been written to the OpenEMR form yet",
    ],
    accent=BLUE,
)

# ============================================================================
# SLIDE 10 — AT3: Confirm-Before-Fill Safeguard
# ============================================================================
at_slide(
    3, "Confirm-Before-Fill Safeguard",
    [
        "With a transcript loaded in the preview, click 'Insert into form'",
        "Observe: browser confirmation dialog appears",
        "Dialog shows the proposed text AND the target field name",
        "Click Cancel — observe that the OpenEMR form is unchanged",
    ],
    [
        "Confirmation dialog fires before any DOM write",
        "Proposed text and field name are visible to the clinician",
        "Cancelling leaves the OpenEMR form exactly as it was",
    ],
    accent=TEAL,
)

# ============================================================================
# SLIDE 11 — AT4: Successful Field Insertion
# ============================================================================
at_slide(
    4, "Successful Field Insertion",
    [
        "With transcript in preview, click 'Insert into form', then confirm",
        "Observe: transcript text appears in the 'Reason for Visit' textarea",
        "Verify: no other form fields (date, checkboxes, selects) were modified",
        "Optionally: save the encounter and verify the text persists",
    ],
    [
        "Field value matches transcript exactly",
        "No other OpenEMR fields are modified",
        "Text triggers React-compatible input/change/blur events",
    ],
    accent=BLUE,
)

# ============================================================================
# SLIDE 12 — AT5: Real Microphone Transcription
# ============================================================================
at_slide(
    5, "Real Microphone Transcription",
    [
        "Click 'Start mic' — browser prompts for microphone permission",
        "Speak: 'Patient presents with shortness of breath and chest tightness'",
        "Click 'Stop' — observe recording pulse stops, status shows 'Transcribing'",
        "Observe: Whisper transcript appears in preview panel within ~2 seconds",
        "(Optional) Show terminal: POST /transcribe_and_extract → NLP entities",
    ],
    [
        "Transcript matches spoken phrase (WER < 10% for clear speech)",
        "Text appears in the preview within 2 seconds of pressing Stop",
        "NLP /extract correctly identifies chief_complaint entity",
    ],
    accent=TEAL,
)

# ============================================================================
# SLIDE 13 — Special Accomplishments
# ============================================================================
slide = new_slide()
slide_header(slide, "Special Accomplishments", accent=GREEN)

acc = [
    ("End-to-End MVP",
     "Voice → Whisper → NLP → OpenEMR field insertion — fully working in 3 iterations"),
    ("Dual NLP Architecture",
     "spaCy fast path (<100ms) + Ollama LLM option with graceful fallback; runs on any hardware"),
    ("Zero OpenEMR Source Changes",
     "Extension attaches non-invasively — no PHP edits, no fork, survives OpenEMR updates"),
    ("Stakeholder-Validated Safety UX",
     "Confirm-before-fill proposed by the team, then explicitly validated by Nirav Merchant"),
    ("Docker-Based Local Dev",
     "Full OpenEMR + FastAPI environment reproducible on any team member's machine"),
    ("CORS-Enabled API",
     "FastAPI service correctly handles cross-origin requests from Chrome extension"),
]

for i, (title, desc) in enumerate(acc):
    col = i % 2
    row = i // 2
    x = Inches(0.4) + col * Inches(6.5)
    y = Inches(1.7) + row * Inches(1.7)
    bw = Inches(6.1)
    bh = Inches(1.55)
    color = TEAL if i % 3 == 0 else (BLUE if i % 3 == 1 else RGBColor(0x44, 0x25, 0x9B))
    add_rect(slide, x, y, Inches(0.06), bh, color)
    add_text(slide, title,
             x + Inches(0.18), y + Inches(0.1), bw - Inches(0.25), Inches(0.5),
             size=18, bold=True, color=color)
    add_text(slide, desc,
             x + Inches(0.18), y + Inches(0.55), bw - Inches(0.25), Inches(0.9),
             size=15, color=SLATE)


# ============================================================================
# SLIDE 14 — Challenges
# ============================================================================
slide = new_slide()
slide_header(slide, "Challenges", accent=ORANGE)

challenges = [
    ("Medical Terminology Accuracy",
     "Whisper base model struggles with drug names and clinical procedures — "
     "visibly lower accuracy on jargon. Model evaluation (MedASR / MedWhisper) is planned.",
     ORANGE),
    ("Scoping Under Pressure",
     "Team faced serious personal circumstances mid-project. Deliberately narrowed MVP to "
     "one field (Reason for Visit) to deliver something real and demo-able.",
     ORANGE),
    ("Three-Part Integration",
     "Chrome extension + local FastAPI + Dockerized OpenEMR must all run simultaneously. "
     "Mid-sprint integration checkpoints (Wednesdays) caught a critical API response mismatch early.",
     ORANGE),
    ("No Automated Test Suite Yet",
     "All testing was manual end-to-end. Automated acceptance tests tied to WER / accuracy / "
     "latency criteria are the first deliverable in the next sprint.",
     ORANGE),
]

for i, (title, desc, color) in enumerate(challenges):
    y = Inches(1.65) + i * Inches(1.35)
    add_rect(slide, Inches(0.4), y, Inches(0.08), Inches(1.2), color)
    add_text(slide, title,
             Inches(0.65), y + Inches(0.05), W - Inches(1.1), Inches(0.45),
             size=19, bold=True, color=color)
    add_text(slide, desc,
             Inches(0.65), y + Inches(0.48), W - Inches(1.1), Inches(0.75),
             size=16, color=WHITE)


# ============================================================================
# SLIDE 15 — Final Takeaways
# ============================================================================
slide = new_slide()
slide_header(slide, "Final Takeaways", accent=TEAL)

takeaways = [
    ("Local AI in Healthcare Works",
     "The full pipeline — microphone → Whisper → NLP → EHR field — runs entirely on the "
     "provider's machine. No cloud, no subscription, HIPAA-aligned by design."),
    ("Scope Aggressively, Ship Something Real",
     "Narrowing to a single customer-validated field (Reason for Visit) delivered a "
     "working demo instead of an incomplete multi-field prototype."),
    ("Stakeholder Feedback Drives Design",
     "Nirav Merchant's patient-safety concern produced the most impactful design decision "
     "in the project (confirm-before-fill). Engage stakeholders early and often."),
    ("Foundation for Expansion",
     "More fields, MedASR/MedWhisper models, WebRTC noise suppression, SOAP notes, and "
     "HIPAA documentation are natural next steps from a solid working base."),
]

for i, (title, desc) in enumerate(takeaways):
    y = Inches(1.65) + i * Inches(1.35)
    color = TEAL if i % 2 == 0 else BLUE
    add_rect(slide, Inches(0.4), y, Inches(0.08), Inches(1.2), color)
    add_text(slide, title,
             Inches(0.65), y + Inches(0.05), W - Inches(1.1), Inches(0.45),
             size=19, bold=True, color=color)
    add_text(slide, desc,
             Inches(0.65), y + Inches(0.48), W - Inches(1.1), Inches(0.75),
             size=16, color=WHITE)

# Closing line
add_text(slide,
         "Thank you.  Questions?",
         Inches(0), H - Inches(0.55), W, Inches(0.5),
         size=20, bold=True, color=TEAL, align=PP_ALIGN.CENTER)


# ============================================================================
# Save
# ============================================================================
out = "CSC436_Team1_FinalPresentation.pptx"
prs.save(out)
print(f"Saved → {out}  ({len(prs.slides)} slides)")
