# ASR & Clinical NLP Service

Local FastAPI service: speech-to-text plus a clinical analysis pipeline.

## Install

```bash
pip install -r requirements.txt
uvicorn api:app --host 127.0.0.1 --port 8000
```

Optional extras:

```bash
# statistical NER — improves PHI name/place detection, enables /extract
pip install spacy && python -m spacy download en_core_web_sm

# local LLM path for SOAP structuring and entity extraction
ollama pull llama3.2:3b
```

The clinical pipeline needs neither. `GET /capabilities` reports what is live.

## Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | health check |
| `GET` | `/capabilities` | available analysis layers |
| `POST` | `/transcribe` | audio → transcript + segment confidence |
| `POST` | `/analyze` | transcript → full clinical analysis |
| `POST` | `/transcribe_and_analyze` | audio → transcript → analysis |
| `POST` | `/extract` | entities only *(legacy, needs spaCy)* |
| `POST` | `/transcribe_and_extract` | audio → entities *(legacy)* |

### `POST /analyze`

```json
{ "transcript": "...", "use_llm": false, "include_phi": true,
  "redact_phi": false, "suggest_icd": true }
```

Returns `soap`, `vitals`, `medications`, `abbreviations`, `negation`,
`findings`, `icd10`, `phi`, `warnings`, `field_mappings`, `timings_ms`.

Example:

```bash
curl -s -X POST http://127.0.0.1:8000/analyze \
  -H 'Content-Type: application/json' \
  -d '{"transcript":"Patient reports headache. She denies chest pain. BP 148 over 92. Impression is likely viral upper respiratory infection. Continue lisinopril 10 mg daily."}'
```

## Modules

| File | Layer |
|---|---|
| `nlp/asr_quality.py` | Whisper decoder confidence, hallucination detection |
| `nlp/soap.py` | SOAP section structuring |
| `nlp/medical.py` | medication correction, vitals, abbreviations, NegEx |
| `nlp/coding.py` | ICD-10 ranking via BM25 |
| `nlp/phi.py` | HIPAA Safe Harbor identifier detection and redaction |
| `nlp/pipeline.py` | orchestration |
| `nlp/field_mapper.py` | analysis output → OpenEMR field names |
| `nlp/extractor.py` | spaCy / Llama entity extraction (optional) |

Technique-by-technique reference: [`../docs/ai-ml-architecture.md`](../docs/ai-ml-architecture.md)

## Configuration

| Variable | Default | Effect |
|---|---|---|
| `WHISPER_MODEL` | `base` | Whisper size: `tiny`, `base`, `small`, `medium`, `large` |

## Tests

```bash
python3 tests/run_tests.py -v
```

45 tests. No Whisper, spaCy, or network required.

## Notes

- Whisper is lazy-loaded: the service starts instantly, the model loads on the
  first transcription request. Run one warm-up transcription before a demo.
- Every layer returns suggestions for clinician confirmation. Nothing writes to
  the chart.
