# User Guide

## What this does

Dictate into an OpenEMR encounter form. The extension records audio, a local
service transcribes and analyses it, and you confirm each field before anything
is written.

Nothing leaves the workstation.

## Setup

### 1. Start the service

```bash
cd asr
pip install -r requirements.txt
uvicorn api:app --host 127.0.0.1 --port 8000
```

Optional, for better name detection in PHI scanning:

```bash
python -m spacy download en_core_web_sm
```

Optional, for LLM-based note structuring:

```bash
ollama pull llama3.2:3b
```

Neither is required. The panel shows which layers are live in its status line.

### 2. Build and load the extension

```bash
npm run check
npm run build
```

Chrome → `chrome://extensions` → Developer Mode → **Load unpacked** →
`dist/extension`

## Using it

1. Open an OpenEMR encounter page. The panel appears at the bottom right.
   It stays hidden on the login screen and on pages with no fillable fields.
2. **Start mic** → dictate → **Stop**.
3. The transcript appears with an ASR confidence bar. Edit it if needed.
4. **Analyze**.
5. Review the field list. Each row shows:
   - the field name as it appears on the page
   - a confidence percentage
   - the value that will be written
   - how the field was matched (real `name` attribute, or inferred from a label)
   - **needs review** when the service was not confident
   - **will overwrite** when the field already has content
6. Tick what you want. Anything flagged for review starts unticked.
7. **Insert N fields** → confirm the dialog.

To put the raw transcript straight into Reason for Visit and skip the analysis,
use **Insert transcript into Reason for Visit**.

## Reading the results

**ASR confidence bar** — the geometric mean of Whisper's token probabilities.
Below about 60% is worth re-listening to.

**Hallucination warning** — Whisper sometimes invents fluent text over silence,
or loops a phrase. When flagged, re-listen before accepting; hallucinated text
reads as fact and carries no marker of doubt.

**Medication warnings** — a mis-heard drug name and its closest formulary
match. A *weak* match warns loudest, because that is the case most needing a
human look. Look-alike/sound-alike pairs are called out separately.

**Abbreviation warnings** — terms on the ISMP error-prone list (QD, U, IU, MS,
HS) are flagged rather than expanded, with the reason they are dangerous.

**Vital sign warnings** — values outside plausible physiologic range, or a
systolic below diastolic. These indicate transcription damage, not clinical
acuity.

**Identifiers detected** — PHI found in the dictation. Clinicians thinking
aloud often say names and dates of birth never meant for the note body.

**Suggested diagnosis codes** — ranked ICD-10 candidates. Findings you negated
("denies chest pain") are excluded. These are candidates for selection, not
codes for billing; the bundled corpus is a curated demo subset.

## Troubleshooting

**"Service offline — demo text only"** — the service is not running, or is on a
different port. Start it, then reload the page.

**Panel does not appear** — the page has no fillable text field, or it is the
login screen. Both are intentional.

**Microphone denied** — use **Demo text**, or paste a transcript into the box.
The full analysis path still runs.

**First transcription is slow** — Whisper loads on first use. Run one warm-up
transcription before a demo.

**"needs review" on everything** — expected when the dictation is short or
ambiguous. Confidence comes from the margin between competing interpretations,
not from the raw score.

## Validation fixtures

```bash
npm run serve:validation
```

- `validation/forms/encounter-soap-vitals.html` — SOAP + vitals with the real
  OpenEMR field names; exercises multi-field resolution
- `validation/forms/contact-reason.html`, `intake-reason.html` — generic forms
- `validation/forms/no-reason-field.html` — the panel must stay hidden

Append `?api=http://127.0.0.1:8100` to point a fixture at another port.

## Limits

- Prototype, not a production OpenEMR plugin. Fields are written through the
  DOM, so OpenEMR's own save validation still applies afterwards.
- Whisper `base` is a general model and mis-hears drug names. Severe cases are
  unrecoverable — in one run "acetaminophen" became "a seed of minifin".
- The ICD-10 corpus is 91 curated codes, not a licensed release.
- Generic web-form support depends on visible labels and `name` attributes.
