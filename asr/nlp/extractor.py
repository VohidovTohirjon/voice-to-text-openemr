"""
NLP Entity Extraction Layer
===========================
Approach A (default): spaCy NER + regex patterns
  - Fast (<100ms), no extra services required
  - Handles structured inputs well (names, emails, phones, dates)
  - Falls back gracefully on ambiguous phrasing

Approach B (opt-in): Local LLM via Ollama (Llama 3.2 3B)
  - Better on conversational/ambiguous phrasing
  - Requires Ollama running locally: https://ollama.com
  - Setup: ollama pull llama3.2:3b
  - ~0.5–1s per call, ~4GB RAM

Both approaches return the same dict schema so the field mapper is unaffected
by which path was taken.
"""

import json
import re

# ---------------------------------------------------------------------------
# spaCy model (lazy-loaded)
# ---------------------------------------------------------------------------

_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        import spacy

        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            raise RuntimeError(
                "spaCy model not found. Run: python -m spacy download en_core_web_sm"
            )
    return _nlp


# ---------------------------------------------------------------------------
# Regex patterns for structured entities
# ---------------------------------------------------------------------------

_PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
    ),
    "phone": re.compile(
        r"\b(?:\+1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b"
    ),
    "zip": re.compile(r"\b\d{5}(?:-\d{4})?\b"),
    "date": re.compile(
        r"\b(?:(?:January|February|March|April|May|June|July|August|September|"
        r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"[\s,]+\d{1,2}[\s,]+\d{4}|\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})\b",
        re.IGNORECASE,
    ),
}

# ---------------------------------------------------------------------------
# Clinical section patterns
# ---------------------------------------------------------------------------

_CLINICAL_SECTIONS: dict[str, re.Pattern] = {
    "chief_complaint": re.compile(
        r"(?:chief[\s_]complaint|cc|presenting[\s_]complaint)[:\s]+(.+?)(?=\n\n|\Z)",
        re.IGNORECASE | re.DOTALL,
    ),
    "assessment": re.compile(
        r"(?:assessment|impression)[:\s]+(.+?)(?=\n\n|\Z)",
        re.IGNORECASE | re.DOTALL,
    ),
    "plan": re.compile(
        r"(?:plan|treatment[\s_]plan|management)[:\s]+(.+?)(?=\n\n|\Z)",
        re.IGNORECASE | re.DOTALL,
    ),
    "medication": re.compile(
        r"(?:medication|med|prescri(?:be|ption))[:\s]+(.+?)(?=\n|\Z)",
        re.IGNORECASE | re.DOTALL,
    ),
    "diagnosis": re.compile(
        r"(?:diagnosis|diagnoses|dx)[:\s]+(.+?)(?=\n|\Z)",
        re.IGNORECASE | re.DOTALL,
    ),
}


# ---------------------------------------------------------------------------
# Approach A: spaCy + regex
# ---------------------------------------------------------------------------


def extract_entities_spacy(transcript: str, context: str = "general") -> dict:
    """
    Rule-based extraction using spaCy NER and regex patterns.

    Returns a dict of { entity_type: { value, confidence } }.
    """
    nlp = _get_nlp()
    doc = nlp(transcript)
    entities: dict = {}

    for ent in doc.ents:
        if ent.label_ == "PERSON" and "name" not in entities:
            parts = ent.text.strip().split()
            entities["name"] = {"value": ent.text.strip(), "confidence": 0.85}
            if len(parts) >= 2:
                entities["first_name"] = {"value": parts[0], "confidence": 0.85}
                entities["last_name"] = {
                    "value": " ".join(parts[1:]),
                    "confidence": 0.85,
                }
        elif ent.label_ == "GPE" and "city" not in entities:
            entities["city"] = {"value": ent.text.strip(), "confidence": 0.75}
        elif ent.label_ in ("DATE", "TIME") and "date" not in entities:
            entities["date"] = {"value": ent.text.strip(), "confidence": 0.80}
        elif ent.label_ == "ORG" and context == "general":
            entities.setdefault(
                "organization", {"value": ent.text.strip(), "confidence": 0.70}
            )

    for entity_type, pattern in _PATTERNS.items():
        if entity_type not in entities:
            match = pattern.search(transcript)
            if match:
                entities[entity_type] = {"value": match.group(0), "confidence": 0.95}

    if context == "clinical":
        for section, pattern in _CLINICAL_SECTIONS.items():
            match = pattern.search(transcript)
            if match:
                entities[section] = {
                    "value": match.group(1).strip(),
                    "confidence": 0.80,
                }

    return entities


# ---------------------------------------------------------------------------
# Approach B: Local LLM via Ollama
# ---------------------------------------------------------------------------


def extract_entities_llm(transcript: str, context: str = "general") -> dict:
    """
    LLM-based extraction via Ollama (Llama 3.2 3B).

    Requires Ollama running locally on port 11434.
    Install: https://ollama.com  |  Model: ollama pull llama3.2:3b
    """
    import requests  # optional dependency

    field_types = (
        "chief_complaint, assessment, plan, medication, diagnosis"
        if context == "clinical"
        else "name, first_name, last_name, email, phone, address, city, state, zip, date_of_birth"
    )

    prompt = (
        "Extract named entities from the transcript below and return ONLY a JSON object. "
        f"Use these entity type keys where applicable: {field_types}. "
        "Each key's value must be an object with 'value' (string) and 'confidence' (0.0–1.0). "
        "Return only valid JSON with no explanation.\n\n"
        f"Transcript: {transcript}\n\nJSON:"
    )

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": "llama3.2:3b", "prompt": prompt, "stream": False},
        timeout=30,
    )
    response.raise_for_status()

    raw = response.json().get("response", "")
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not json_match:
        raise ValueError(f"No JSON found in LLM response: {raw!r}")

    return json.loads(json_match.group(0))


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def extract_entities(
    transcript: str,
    context: str = "general",
    use_llm: bool = False,
) -> dict:
    """
    Extract entities from a transcript.

    Args:
        transcript: Raw text from ASR.
        context:    'general' (names, addresses, dates) or
                    'clinical' (SOAP fields, medications, diagnoses).
        use_llm:    If True, use Ollama LLM (Approach B) with spaCy fallback.

    Returns:
        Dict of { entity_type: { value, confidence } }.
        May include '_fallback_reason' key if LLM failed and spaCy was used.
    """
    if use_llm:
        try:
            return extract_entities_llm(transcript, context)
        except Exception as exc:
            result = extract_entities_spacy(transcript, context)
            result["_fallback_reason"] = str(exc)
            return result

    return extract_entities_spacy(transcript, context)
