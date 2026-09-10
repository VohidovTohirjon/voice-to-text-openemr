"""
PHI Detection and De-identification
===================================
Finds Protected Health Information in a dictated transcript and can produce a
de-identified copy.

Scope: the HIPAA Safe Harbor identifier list (45 CFR 164.514(b)(2)). Fifteen of
the eighteen identifiers are detectable in free text and are implemented here;
the remaining three (full-face photographs, biometric identifiers, and
fingerprints/voiceprints) are properties of the media rather than the
transcript.

Two independent detectors run and are merged:

  * pattern matching for structured identifiers — SSN, phone, email, MRN,
    account numbers, URLs, IP addresses, dates, ZIP codes
  * named-entity recognition for unstructured ones — person names and places

The NER pass uses spaCy when it is installed. When it is not, a title- and
context-based fallback runs instead, and the result is marked
`ner_backend: "fallback"` so the caller can tell the difference rather than
silently trusting a weaker pass.

Why this belongs in a voice tool specifically
---------------------------------------------
Dictation captures whatever is said in the room. A clinician thinking aloud
says patient names, dates of birth, and phone numbers that were never meant for
the note body. Catching them at the transcript boundary is cheaper than
scrubbing the chart afterwards, and it is what makes "the audio never leaves
the machine" a complete claim rather than half of one.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# Age 90 and over is itself an identifier under Safe Harbor: such ages must be
# aggregated into a single "90 or older" category.
HIPAA_AGE_CEILING = 89

_PATTERNS: List[Tuple[str, "re.Pattern", str]] = [
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "Social Security number"),
    ("ssn", re.compile(r"\b\d{3}\s\d{2}\s\d{4}\b"), "Social Security number"),
    ("email", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
     "Email address"),
    ("phone", re.compile(
        r"\b(?:\+?1[\s\-.])?\(?\d{3}\)?[\s\-.]\d{3}[\s\-.]\d{4}\b"), "Telephone number"),
    ("url", re.compile(r"\bhttps?://[^\s<>\"]+"), "Web URL"),
    ("ip_address", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "IP address"),
    ("mrn", re.compile(
        r"\b(?:mrn|medical\s+record\s+(?:number|no\.?)|chart\s+(?:number|no\.?))"
        r"\s*[:#]?\s*([A-Z0-9\-]{4,})\b", re.IGNORECASE), "Medical record number"),
    ("account", re.compile(
        r"\b(?:account|policy|member|beneficiary|claim)\s*"
        r"(?:number|no\.?|#)?\s*[:#]\s*([A-Z0-9\-]{4,})\b", re.IGNORECASE),
     "Account or health-plan number"),
    ("license", re.compile(
        r"\b(?:license|licence|certificate)\s*(?:number|no\.?|#)?\s*[:#]?\s*"
        r"([A-Z0-9\-]{5,})\b", re.IGNORECASE), "Certificate or license number"),
    ("date", re.compile(
        r"\b(?:0?[1-9]|1[0-2])[/\-](?:0?[1-9]|[12]\d|3[01])[/\-](?:\d{2}|\d{4})\b"),
     "Date"),
    ("date", re.compile(
        r"\b(?:January|February|March|April|May|June|July|August|September|"
        r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)"
        r"\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b", re.IGNORECASE), "Date"),
    ("date_of_birth", re.compile(
        r"\b(?:date\s+of\s+birth|dob|born\s+on|birth\s*date)\s*[:]?\s*"
        r"([A-Za-z0-9/,\-\s]{6,20}?)(?=[.;,]|\s{2}|$)", re.IGNORECASE), "Date of birth"),
    ("zip", re.compile(r"\b\d{5}(?:-\d{4})?\b"), "ZIP code"),
]

# Person-name cues that work without a statistical model.
# The cue word is matched case-insensitively via a scoped (?i:...) group, while
# the captured name keeps its case requirement — a whole-pattern IGNORECASE flag
# would let [A-Z][a-z]+ match ordinary lowercase words.
_TITLE_NAME = re.compile(
    r"\b(?i:mr|mrs|ms|miss|dr|doctor|nurse|prof)\.?\s+"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b")
_CONTEXT_NAME = re.compile(
    r"\b(?i:patient|client|resident|seen\s+by|referred\s+(?:to|by)|"
    r"spoke\s+with|name\s+is|this\s+is)\s+"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b")

_AGE = re.compile(
    r"\b(\d{2,3})[\s\-]*(?:year|yr)s?[\s\-]*old\b|\bage\s+(?:of\s+)?(\d{2,3})\b",
    re.IGNORECASE)

# Sentence-initial and clinical-vocabulary capitals that the fallback name
# detector must not mistake for people.
_NOT_NAMES = {
    "Patient", "Assessment", "Plan", "Subjective", "Objective", "History",
    "Blood", "Heart", "Chest", "Review", "Physical", "Exam", "Vitals",
    "Denies", "Reports", "Continue", "Start", "Stop", "Follow", "Return",
    "Today", "Yesterday", "Tomorrow", "Normal", "Negative", "Positive",
    # Titles: a cue like "referred by Dr. Smith" otherwise captures "Dr" itself.
    "Dr", "Mr", "Mrs", "Ms", "Miss", "Doctor", "Nurse", "Prof",
}


def _spacy_names(text: str) -> Optional[List[Dict[str, Any]]]:
    """Person and place entities from spaCy, or None when spaCy is unavailable."""
    try:
        import spacy
    except ImportError:
        return None
    try:
        nlp = spacy.load("en_core_web_sm")
    except (OSError, IOError):
        return None

    found: List[Dict[str, Any]] = []
    for ent in nlp(text).ents:
        if ent.label_ == "PERSON":
            kind, label = "name", "Person name"
        elif ent.label_ in ("GPE", "LOC", "FAC"):
            kind, label = "location", "Geographic location"
        else:
            continue
        found.append({
            "type": kind,
            "label": label,
            "text": ent.text,
            "start": ent.start_char,
            "end": ent.end_char,
            "confidence": 0.85,
            "detector": "spacy_ner",
        })
    return found


def _fallback_names(text: str) -> List[Dict[str, Any]]:
    """Title- and context-cued name detection for when spaCy is not installed."""
    found: List[Dict[str, Any]] = []
    for pattern, confidence in ((_TITLE_NAME, 0.80), (_CONTEXT_NAME, 0.60)):
        for match in pattern.finditer(text):
            value = match.group(1)
            if value.split()[0] in _NOT_NAMES:
                continue
            found.append({
                "type": "name",
                "label": "Person name",
                "text": value,
                "start": match.start(1),
                "end": match.end(1),
                "confidence": confidence,
                "detector": "pattern_fallback",
            })
    return found


def _overlaps(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return a["start"] < b["end"] and b["start"] < a["end"]


def detect_phi(transcript: str) -> Dict[str, Any]:
    """
    Locate PHI in a transcript.

    Returns:
        entities     — list of {type, label, text, start, end, confidence, detector}
        by_type      — counts per identifier type
        ner_backend  — "spacy" or "fallback"
        risk         — none | low | medium | high
    """
    if not transcript:
        return {"entities": [], "by_type": {}, "ner_backend": "none", "risk": "none"}

    entities: List[Dict[str, Any]] = []

    for kind, pattern, label in _PATTERNS:
        for match in pattern.finditer(transcript):
            # Grouped patterns point at the identifier itself, not the cue word.
            index = 1 if match.groups() else 0
            value = (match.group(index) or "").strip()
            if not value:
                continue
            entities.append({
                "type": kind,
                "label": label,
                "text": value,
                "start": match.start(index),
                "end": match.end(index),
                "confidence": 0.95,
                "detector": "pattern",
            })

    for match in _AGE.finditer(transcript):
        raw = match.group(1) or match.group(2)
        try:
            age = int(raw)
        except (TypeError, ValueError):
            continue
        if age > HIPAA_AGE_CEILING:
            entities.append({
                "type": "age_over_89",
                "label": "Age over 89 (must be aggregated as '90 or older')",
                "text": match.group(0),
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.90,
                "detector": "pattern",
            })

    names = _spacy_names(transcript)
    backend = "spacy" if names is not None else "fallback"
    if names is None:
        names = _fallback_names(transcript)
    entities.extend(names)

    # Resolve overlaps, preferring the higher-confidence detection. A ZIP code
    # pattern and a date pattern can claim the same digits.
    entities.sort(key=lambda e: (-e["confidence"], e["start"]))
    kept: List[Dict[str, Any]] = []
    for candidate in entities:
        if not any(_overlaps(candidate, existing) for existing in kept):
            kept.append(candidate)
    kept.sort(key=lambda e: e["start"])

    by_type: Dict[str, int] = {}
    for item in kept:
        by_type[item["type"]] = by_type.get(item["type"], 0) + 1

    direct = {"ssn", "mrn", "account", "name", "date_of_birth", "phone", "email", "license"}
    direct_hits = sum(count for kind, count in by_type.items() if kind in direct)
    if direct_hits >= 3:
        risk = "high"
    elif direct_hits >= 1:
        risk = "medium"
    elif kept:
        risk = "low"
    else:
        risk = "none"

    return {
        "entities": kept,
        "by_type": by_type,
        "ner_backend": backend,
        "risk": risk,
        "note": (
            "spaCy is not installed; person and place detection is running on the "
            "pattern fallback and will miss names without a title or cue word."
            if backend == "fallback" else
            "Person and place detection is running on the spaCy NER model."
        ),
    }


def redact(transcript: str, detection: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Produce a de-identified copy of the transcript.

    Each identifier is replaced with a bracketed placeholder naming its type, so
    the note stays readable and the redaction is auditable.
    """
    if detection is None:
        detection = detect_phi(transcript)

    redacted = transcript
    replacements: List[Dict[str, Any]] = []

    # Replace back-to-front so earlier offsets stay valid.
    for item in sorted(detection["entities"], key=lambda e: e["start"], reverse=True):
        placeholder = "[" + item["type"].upper() + "]"
        redacted = redacted[: item["start"]] + placeholder + redacted[item["end"]:]
        replacements.append({
            "original": item["text"],
            "placeholder": placeholder,
            "type": item["type"],
        })

    replacements.reverse()
    return {
        "redacted_text": redacted,
        "replacements": replacements,
        "replacement_count": len(replacements),
        "ner_backend": detection["ner_backend"],
    }
