import os
import tempfile

import whisper
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from nlp.extractor import extract_entities
from nlp.field_mapper import map_entities_to_fields

app = FastAPI(title="ASR Service")

# Lazy-load Whisper so startup is fast even if /extract is all that's needed
_whisper_model = None


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = whisper.load_model("base")
    return _whisper_model


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------


class ExtractRequest(BaseModel):
    transcript: str
    context: str = "general"   # 'general' or 'clinical'
    use_llm: bool = False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/")
def root():
    return {"message": "ASR service is running"}


@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe an audio file and return raw text."""
    suffix = os.path.splitext(file.filename)[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        result = _get_whisper_model().transcribe(tmp_path)
        return {"transcription": result["text"].strip()}
    finally:
        os.remove(tmp_path)


@app.post("/extract")
def extract_from_transcript(req: ExtractRequest):
    """
    Extract entities from an existing transcript and return field-fill mappings.

    Body:
        transcript  — raw text (e.g. from /transcribe)
        context     — 'general' (default) or 'clinical'
        use_llm     — if true, use Ollama LLM with spaCy fallback

    Returns:
        entities       — { entity_type: { value, confidence } }
        field_mappings — sorted list of field-fill candidates
        context        — echoed back for the caller
    """
    if req.context not in ("general", "clinical"):
        raise HTTPException(status_code=400, detail="context must be 'general' or 'clinical'")

    entities = extract_entities(req.transcript, context=req.context, use_llm=req.use_llm)
    mappings = map_entities_to_fields(entities)

    return {
        "entities": entities,
        "field_mappings": mappings,
        "context": req.context,
    }


@app.post("/transcribe_and_extract")
async def transcribe_and_extract(
    file: UploadFile = File(...),
    context: str = "general",
    use_llm: bool = False,
):
    """
    Full pipeline: audio file → transcript → entities → field mappings.

    Query params:
        context  — 'general' (default) or 'clinical'
        use_llm  — if true, use Ollama LLM with spaCy fallback

    Returns:
        transcription  — raw transcript text
        entities       — { entity_type: { value, confidence } }
        field_mappings — sorted list of field-fill candidates
        context        — echoed back
    """
    if context not in ("general", "clinical"):
        raise HTTPException(status_code=400, detail="context must be 'general' or 'clinical'")

    suffix = os.path.splitext(file.filename)[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        result = _get_whisper_model().transcribe(tmp_path)
        transcript = result["text"].strip()
    finally:
        os.remove(tmp_path)

    entities = extract_entities(transcript, context=context, use_llm=use_llm)
    mappings = map_entities_to_fields(entities)

    return {
        "transcription": transcript,
        "entities": entities,
        "field_mappings": mappings,
        "context": context,
    }
