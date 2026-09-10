"""
ASR + Clinical NLP Service
==========================
Local FastAPI service behind the OpenEMR voice-to-text extension.

Endpoints
---------
    GET  /                       health check
    GET  /capabilities           which analysis layers this deployment has

    POST /transcribe             audio -> transcript + per-segment confidence
    POST /analyze                transcript -> full clinical analysis
    POST /transcribe_and_analyze audio -> transcript -> full clinical analysis

    POST /extract                transcript -> entities + field mappings   (legacy)
    POST /transcribe_and_extract audio -> entities + field mappings        (legacy)

Everything runs on the machine that serves this process. No audio, transcript,
or derived text is sent anywhere.

The two legacy endpoints predate the clinical pipeline and are kept so existing
callers keep working; new work should use /analyze.
"""

import os
import tempfile

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from nlp.extractor import extract_entities
from nlp.field_mapper import map_entities_to_fields
from nlp.pipeline import analyze as run_analysis
from nlp.pipeline import capabilities as describe_capabilities

app = FastAPI(
    title="OpenEMR ASR & Clinical NLP Service",
    version="0.2.0",
    description="Local speech-to-text with a clinical analysis pipeline.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Whisper is loaded lazily so the process starts instantly and the text-only
# endpoints stay usable on machines where the model has not been downloaded.
_whisper_model = None
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL", "base")


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        import whisper
        _whisper_model = whisper.load_model(WHISPER_MODEL_SIZE)
    return _whisper_model


def _transcribe_upload(file: UploadFile, audio_bytes: bytes):
    """
    Write the upload to a temp file and run Whisper over it.

    Returns (transcript, segments). Segments carry the decoding statistics the
    quality layer needs — avg_logprob, compression_ratio, no_speech_prob — which
    is why the raw result is unpacked here rather than just its text.
    """
    suffix = os.path.splitext(file.filename or "")[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        result = _get_whisper_model().transcribe(tmp_path)
    finally:
        os.remove(tmp_path)

    segments = [
        {
            "start": seg.get("start"),
            "end": seg.get("end"),
            "text": seg.get("text", ""),
            "avg_logprob": seg.get("avg_logprob"),
            "compression_ratio": seg.get("compression_ratio"),
            "no_speech_prob": seg.get("no_speech_prob"),
        }
        for seg in result.get("segments", [])
    ]
    return result.get("text", "").strip(), segments, result.get("language")


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ExtractRequest(BaseModel):
    transcript: str
    context: str = "general"   # 'general' or 'clinical'
    use_llm: bool = False


class AnalyzeRequest(BaseModel):
    transcript: str
    use_llm: bool = False        # route SOAP structuring through local Llama
    include_phi: bool = True
    redact_phi: bool = False
    suggest_icd: bool = True


# ---------------------------------------------------------------------------
# Health and capability
# ---------------------------------------------------------------------------


@app.get("/")
def root():
    return {
        "service": "OpenEMR ASR & Clinical NLP",
        "version": "0.2.0",
        "status": "running",
        "whisper_model": WHISPER_MODEL_SIZE,
        "whisper_loaded": _whisper_model is not None,
    }


@app.get("/capabilities")
def capabilities():
    """
    Report which analysis layers this deployment actually has.

    The extension calls this on start-up so the UI can hide features that are
    unavailable rather than failing at the moment the clinician clicks them.
    """
    info = describe_capabilities()
    info["whisper"] = {
        "available": True,
        "model": WHISPER_MODEL_SIZE,
        "loaded": _whisper_model is not None,
        "note": "Loaded on first transcription request.",
    }
    return info


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------


@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Transcribe audio and return the text plus per-segment decoding confidence.

    `transcription` is kept as the top-level key for backwards compatibility
    with the existing extension build.
    """
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")

    transcript, segments, language = _transcribe_upload(file, audio_bytes)

    from nlp.asr_quality import analyze_segments, low_confidence_spans
    quality = analyze_segments(segments)
    quality["low_confidence_spans"] = low_confidence_spans(quality)

    return {
        "transcription": transcript,
        "language": language,
        "segments": segments,
        "quality": quality,
    }


# ---------------------------------------------------------------------------
# Clinical analysis
# ---------------------------------------------------------------------------


@app.post("/analyze")
def analyze_transcript(req: AnalyzeRequest):
    """
    Run the full clinical pipeline over an existing transcript.

    Returns SOAP structure, vitals, medication checks, abbreviation expansions,
    negation status, ICD-10 candidates, PHI findings, warnings, and OpenEMR
    field mappings. Every item is a suggestion for clinician confirmation.
    """
    if not req.transcript or not req.transcript.strip():
        raise HTTPException(status_code=400, detail="transcript must not be empty.")

    return run_analysis(
        req.transcript,
        segments=None,
        use_llm=req.use_llm,
        include_phi=req.include_phi,
        redact_phi=req.redact_phi,
        suggest_icd=req.suggest_icd,
    )


@app.post("/transcribe_and_analyze")
async def transcribe_and_analyze(
    file: UploadFile = File(...),
    use_llm: bool = Query(False),
    include_phi: bool = Query(True),
    redact_phi: bool = Query(False),
    suggest_icd: bool = Query(True),
):
    """
    Full path: audio -> transcript -> clinical analysis, in one request.

    The Whisper segments are handed to the analysis so the ASR quality layer can
    flag low-confidence and hallucinated spans, which is not possible when only
    the transcript text is available.
    """
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")

    transcript, segments, language = _transcribe_upload(file, audio_bytes)

    analysis = run_analysis(
        transcript,
        segments=segments,
        use_llm=use_llm,
        include_phi=include_phi,
        redact_phi=redact_phi,
        suggest_icd=suggest_icd,
    )
    analysis["language"] = language
    analysis["segments"] = segments
    return analysis


# ---------------------------------------------------------------------------
# Legacy entity endpoints
# ---------------------------------------------------------------------------


@app.post("/extract")
def extract_from_transcript(req: ExtractRequest):
    """
    Entity extraction only. Superseded by /analyze; kept for existing callers.

    Requires spaCy. When spaCy is not installed this returns 503 with the
    install command, rather than a 500 from deep inside the extractor.
    """
    if req.context not in ("general", "clinical"):
        raise HTTPException(status_code=400, detail="context must be 'general' or 'clinical'")

    try:
        entities = extract_entities(req.transcript, context=req.context, use_llm=req.use_llm)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail=("spaCy is not installed. Run: pip install spacy && "
                    "python -m spacy download en_core_web_sm — or use /analyze, "
                    "which does not require spaCy."),
        )

    return {
        "entities": entities,
        "field_mappings": map_entities_to_fields(entities),
        "context": req.context,
    }


@app.post("/transcribe_and_extract")
async def transcribe_and_extract(
    file: UploadFile = File(...),
    context: str = Query("general"),
    use_llm: bool = Query(False),
):
    """Audio -> entities. Superseded by /transcribe_and_analyze."""
    if context not in ("general", "clinical"):
        raise HTTPException(status_code=400, detail="context must be 'general' or 'clinical'")

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")

    transcript, _segments, _language = _transcribe_upload(file, audio_bytes)

    try:
        entities = extract_entities(transcript, context=context, use_llm=use_llm)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail=("spaCy is not installed. Use /transcribe_and_analyze, which "
                    "does not require spaCy."),
        )

    return {
        "transcription": transcript,
        "entities": entities,
        "field_mappings": map_entities_to_fields(entities),
        "context": context,
    }
