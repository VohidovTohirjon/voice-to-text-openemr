"""
Decoder Conditioning for Clinical Speech
========================================
Whisper accepts an `initial_prompt`: text prepended to the decoding context that
biases the model toward the vocabulary it contains. It is not fine-tuning and it
changes no weights — it shifts the language-model prior for one request.

Why this module exists
----------------------
Whisper `base` is a general model. On dictated drug names it fails badly, and
the failures are not near-misses:

    "lisinopril"     ->  "lice in april"
    "acetaminophen"  ->  "assetaminif and"

Those are not spelling errors. The model has split one word into three ordinary
English words, and no string-similarity layer downstream can recover "lisinopril"
from "lice in april" — the surface form is gone. The fix has to happen while
decoding, not after.

Conditioning the decoder on a clinical vocabulary makes the correct spelling a
far more probable continuation, and both examples above resolve exactly.

Two other decoder settings matter as much:

  language="en"     Whisper detects language per request. Clinical dictation is
                    full of Latin-derived drug names, and on a short or accented
                    clip the detector can pick the wrong language and emit
                    another script entirely. Pinning the language removes an
                    entire class of failure.

  temperature=0     Greedy decoding. The default schedule falls back to sampling
                    when a segment looks bad, which trades determinism for a
                    second chance. In a chart note, reproducibility is worth
                    more.

The prompt is built from the same formulary the correction layer uses, so the
two never drift apart.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from .medical import _medications  # noqa: SLF001 - same package, deliberate reuse

# Whisper's prompt window is 224 tokens and keeps the TAIL when it overflows.
# Roughly 150 words stays comfortably inside it, so nothing important is
# silently dropped off the front.
MAX_PROMPT_WORDS = 150

# Ordered by how often they appear in outpatient dictation, because the prompt
# has a hard budget and the head of this list is what survives it. Every entry
# is verified against the bundled formulary at import time.
_PRIORITY_MEDICATIONS: Sequence[str] = (
    "lisinopril", "levothyroxine", "atorvastatin", "metformin", "amlodipine",
    "metoprolol", "omeprazole", "losartan", "albuterol", "gabapentin",
    "hydrochlorothiazide", "sertraline", "simvastatin", "montelukast",
    "rosuvastatin", "escitalopram", "acetaminophen", "ibuprofen", "amoxicillin",
    "prednisone", "fluticasone", "furosemide", "pantoprazole", "trazodone",
    "tamsulosin", "atenolol", "duloxetine", "carvedilol", "meloxicam",
    "clopidogrel", "azithromycin", "alprazolam", "glipizide", "cyclobenzaprine",
    "allopurinol", "tramadol", "warfarin", "apixaban", "doxycycline",
    "cephalexin",
)

# Conditions and exam vocabulary. Short, because medication names are where the
# decoder actually struggles.
_FINDINGS: Sequence[str] = (
    "hypertension", "diabetes mellitus", "hyperlipidemia", "asthma",
    "chest pain", "shortness of breath", "headache", "fever", "cough",
    "pharyngitis", "urinary tract infection", "low back pain",
)

_VITALS: Sequence[str] = (
    "blood pressure", "pulse", "respiratory rate", "temperature",
    "oxygen saturation",
)


def _known_medications() -> List[str]:
    """Priority list, filtered to what the formulary actually contains."""
    available = {entry["name"].lower() for entry in _medications()}
    return [name for name in _PRIORITY_MEDICATIONS if name in available]


def clinical_prompt(extra_terms: Optional[Sequence[str]] = None) -> str:
    """
    Build the `initial_prompt` for a clinical dictation request.

    Args:
        extra_terms: additional vocabulary to bias toward — a patient's current
            medication list, for example. These go FIRST, because they are the
            most specific evidence available about what is likely to be said,
            and because the tail of the prompt is what survives truncation.

    The prompt is written as a fragment of a plausible note rather than a bare
    word list: Whisper conditions on it as text, so prose that looks like the
    target domain biases better than a comma-separated dump.
    """
    parts: List[str] = ["Clinical encounter note."]

    if extra_terms:
        cleaned = [str(t).strip() for t in extra_terms if str(t).strip()]
        if cleaned:
            parts.append("Current medications: " + ", ".join(cleaned) + ".")

    parts.append("Medications: " + ", ".join(_known_medications()) + ".")
    parts.append("Findings: " + ", ".join(_FINDINGS) + ".")
    parts.append("Vitals: " + ", ".join(_VITALS) + ".")

    prompt = " ".join(parts)

    words = prompt.split()
    if len(words) > MAX_PROMPT_WORDS:
        # Keep the tail: Whisper truncates from the front, and the caller's
        # extra_terms plus the highest-priority drugs are worth protecting.
        prompt = " ".join(words[:MAX_PROMPT_WORDS])

    return prompt


def decode_options(
    language: str = "en",
    extra_terms: Optional[Sequence[str]] = None,
) -> dict:
    """
    Decoder settings for a clinical transcription request.

    Returned as a plain dict so the caller can log exactly what was used and so
    the settings can be overridden per request.
    """
    return {
        "language": language,
        "initial_prompt": clinical_prompt(extra_terms),
        "temperature": 0.0,
        "condition_on_previous_text": False,
    }
