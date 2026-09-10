# Voice-to-Text OpenEMR Integration

Dictate into an OpenEMR encounter form. Speech becomes text, text becomes
structured clinical data, and a clinician confirms every field before anything
is written to the chart.

Everything runs on the local machine — no audio, transcript, or derived text
leaves the workstation.

## What it does

1. **Record** in the browser, from a floating panel on the encounter page.
2. **Transcribe** with Whisper, running locally, returning per-segment
   confidence and hallucination flags.
3. **Analyze** the transcript into SOAP sections, vitals, medications,
   diagnosis codes, and PHI findings.
4. **Confirm** — the panel lists each proposed field with a confidence score.
   Anything flagged for review starts unticked.
5. **Fill** the confirmed fields, verifying each write.

## AI/ML layers

| # | Layer | Technique | File |
|---|---|---|---|
| 1 | Speech recognition | Whisper `base`, transformer encoder–decoder | `asr/api.py` |
| 2 | ASR quality & hallucination detection | Whisper decoder statistics | `asr/nlp/asr_quality.py` |
| 3 | SOAP structuring | Cue-phrase scoring classifier (LLM optional) | `asr/nlp/soap.py` |
| 4 | Medication correction | Soundex + edit distance over a formulary | `asr/nlp/medical.py` |
| 5 | Vitals extraction | Regex + unit normalisation + range validation | `asr/nlp/medical.py` |
| 6 | Negation detection | NegEx, sentence-scoped | `asr/nlp/medical.py` |
| 7 | ICD-10 suggestion | Okapi BM25 information retrieval | `asr/nlp/coding.py` |
| 8 | PHI detection | Pattern matching + NER | `asr/nlp/phi.py` |
| 9 | Entity extraction *(optional)* | spaCy NER, or local Llama 3.2 via Ollama | `asr/nlp/extractor.py` |

Layers 1 and 9 are neural networks. Layer 2 reads a neural network's internal
state. Layers 3–8 are classical algorithms — stated plainly, because "AI" that
turns out to be a regex is worse than a regex described honestly.

Full technical reference: **[docs/ai-ml-architecture.md](docs/ai-ml-architecture.md)**

## Project structure

```
asr/                  local speech-to-text and clinical NLP service
  api.py              FastAPI endpoints
  nlp/                the analysis layers
    asr_quality.py    decoder confidence, hallucination detection
    soap.py           SOAP section structuring
    medical.py        drugs, vitals, abbreviations, negation
    coding.py         ICD-10 ranking (BM25)
    phi.py            HIPAA Safe Harbor identifier detection
    pipeline.py       orchestration; the negation -> coding edge
    field_mapper.py   analysis output -> OpenEMR field names
    extractor.py      spaCy / Llama entity extraction (optional)
    data/             formulary, abbreviations, ICD-10 corpus
  tests/run_tests.py  45 dependency-free tests
extension/            Chrome MV3 content scripts
openemr/              modified OpenEMR files
validation/           test fixtures and checklists
docs/                 setup, usage, architecture
```

## Quick start

**1. Start the service**

```bash
cd asr
pip install -r requirements.txt
uvicorn api:app --host 127.0.0.1 --port 8000
```

The clinical pipeline is pure Python and needs no ML dependencies. Whisper is
required only for the audio endpoints; spaCy is optional and adds NER quality.
`GET /capabilities` reports which layers are live.

**2. Build and load the extension**

```bash
npm run check
npm run build
```

Chrome → `chrome://extensions` → Developer Mode → **Load unpacked** →
`dist/extension`

**3. Use it**

Open a local OpenEMR encounter page. The panel appears when a fillable form is
present, and stays hidden on the login screen.

Record → Stop → **Analyze** → review the ticks → **Insert**.

No microphone? **Demo text** loads a representative transcript so the full
analysis path still runs.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | health check |
| `GET` | `/capabilities` | which analysis layers are available |
| `POST` | `/transcribe` | audio → transcript + segment confidence |
| `POST` | `/analyze` | transcript → full clinical analysis |
| `POST` | `/transcribe_and_analyze` | audio → transcript → analysis |
| `POST` | `/extract` | entities only *(legacy, needs spaCy)* |
| `POST` | `/transcribe_and_extract` | audio → entities *(legacy)* |

## Tests

```bash
npm run check          # syntax, manifest, and the Python test suite
python3 asr/tests/run_tests.py -v
```

45 tests, no external dependencies — they run without Whisper, spaCy, or a
network.

## Validation fixtures

```bash
npm run serve:validation
```

Then open:

- `validation/forms/encounter-soap-vitals.html` — SOAP + vitals, using the real
  OpenEMR field names. Exercises multi-field resolution.
- `validation/forms/contact-reason.html`, `intake-reason.html` — generic forms
- `validation/forms/no-reason-field.html` — negative case; the panel must stay
  hidden

Add `?api=http://127.0.0.1:8100` to point a fixture at a service on another
port.

See `validation/test-matrix.md` and `validation/openemr-encounter-checklist.md`.

## Safety posture

- Every layer produces **suggestions**. Nothing writes to the chart on its own.
- Low-confidence suggestions start **unticked** — the operator opts in.
- Medication corrections are never applied silently; LASA pairs are flagged.
- ISMP error-prone abbreviations raise a warning rather than being expanded.
- Negated findings are excluded from code suggestions.
- The ICD-10 corpus is a 91-code curated demo subset, **not** a licensed
  ICD-10-CM release. Replace it with the current CMS/CDC files before billing
  use.

## Status and next steps

Working prototype with a complete local pipeline and a demo-ready extension.

Next:

- **Evaluate a medical-domain ASR model.** Whisper `base` transcribed
  "acetaminophen" as *"a seed of minifin"* in a real run — a failure no string
  matching can recover, and the concrete argument for a domain-adapted model.
- Replace the curated ICD-10 subset with a licensed release, and the formulary
  with an RxNorm extract.
- Write back through OpenEMR's form APIs rather than the DOM.
