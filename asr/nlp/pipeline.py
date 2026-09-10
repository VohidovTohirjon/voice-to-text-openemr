"""
Clinical Analysis Pipeline
==========================
Runs every analysis layer over one transcript and returns a single result the
UI can render without further assembly.

Order matters, because later stages consume earlier ones:

    transcript
        |
        +-- asr_quality      decoding confidence, hallucination flags
        +-- phi              identifiers present in the dictation
        +-- soap             section structure
        |     |
        +-----+-- vitals     parsed out of the Objective text
        |     |
        |     +-- negation   assertion status of findings, sentence-scoped
        |           |
        |           +-- icd10   coded from AFFIRMED findings only
        |
        +-- medications      formulary matching over the whole note
        +-- abbreviations    expansion candidates
        |
        +-- field_mappings   everything above, addressed to OpenEMR fields

The negation -> coding edge is the one that matters clinically. "Denies chest
pain" contains the phrase "chest pain", and a coder that ignores assertion
status will happily suggest R07.9 for a patient who explicitly does not have
it. Filtering negated findings before coding is what makes the suggestions
safe to show.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from . import asr_quality, coding, medical, phi, soap
from .field_mapper import map_entities_to_fields

# Findings mentioned only as negatives still get reported, so the clinician can
# see the system understood the negation rather than missed the phrase.
_MAX_CODES = 5


def _finding_vocabulary() -> List[str]:
    """
    Clinical findings to test for negation.

    The ICD corpus synonyms already are a curated finding lexicon, so it is
    reused here instead of maintaining a second list that could drift from it.
    """
    index = coding._build_index()  # noqa: SLF001 - same package, deliberate reuse
    terms = set()
    for doc in index["documents"]:
        for phrase in doc["synonyms"]:
            if 3 < len(phrase) <= 30:
                terms.add(phrase.lower())
    return sorted(terms)


def analyze(
    transcript: str,
    segments: Optional[List[Dict[str, Any]]] = None,
    use_llm: bool = False,
    include_phi: bool = True,
    redact_phi: bool = False,
    suggest_icd: bool = True,
) -> Dict[str, Any]:
    """
    Run the full clinical analysis.

    Args:
        transcript:  text from ASR (or typed).
        segments:    Whisper's per-segment stats, when available.
        use_llm:     route SOAP structuring through the local Llama model.
        include_phi: run PHI detection.
        redact_phi:  additionally return a de-identified transcript.
        suggest_icd: run ICD-10 candidate ranking.

    Returns a dict with one key per layer, plus `field_mappings`, `warnings`
    and `timings_ms`.
    """
    started = time.perf_counter()
    timings: Dict[str, float] = {}
    warnings: List[Dict[str, str]] = []

    def _timed(name: str, function, *args, **kwargs):
        mark = time.perf_counter()
        try:
            return function(*args, **kwargs)
        finally:
            timings[name] = round((time.perf_counter() - mark) * 1000, 2)

    result: Dict[str, Any] = {"transcript": transcript}

    if not transcript or not transcript.strip():
        return {
            "transcript": transcript or "",
            "empty": True,
            "warnings": [{"level": "info", "message": "Transcript is empty."}],
            "field_mappings": [],
            "timings_ms": {"total": 0.0},
        }

    # --- ASR decoding quality -------------------------------------------------
    if segments:
        quality = _timed("asr_quality", asr_quality.analyze_segments, segments)
        quality["low_confidence_spans"] = asr_quality.low_confidence_spans(quality)
        result["asr_quality"] = quality
        if quality["hallucination_risk"] in ("medium", "high"):
            warnings.append({
                "level": "high" if quality["hallucination_risk"] == "high" else "medium",
                "message": (
                    "{0} of {1} segments show hallucination signatures. Re-listen "
                    "before accepting this transcript.".format(
                        quality["summary"]["hallucination_suspected_count"],
                        quality["summary"]["segment_count"])
                ),
            })
        elif quality["overall_confidence"] < asr_quality.REVIEW_CONFIDENCE:
            warnings.append({
                "level": "medium",
                "message": "Overall ASR confidence is {0:.0%}; verify the transcript.".format(
                    quality["overall_confidence"]),
            })

    # --- PHI ------------------------------------------------------------------
    if include_phi:
        detection = _timed("phi", phi.detect_phi, transcript)
        result["phi"] = detection
        if detection["risk"] in ("medium", "high"):
            warnings.append({
                "level": detection["risk"],
                "message": "{0} identifier(s) detected in the dictation.".format(
                    len(detection["entities"])),
            })
        if redact_phi:
            result["redacted"] = _timed("redact", phi.redact, transcript, detection)

    # --- SOAP structure -------------------------------------------------------
    structured = _timed("soap", soap.structure_note, transcript, use_llm)
    rendered = soap.render_sections(structured)
    result["soap"] = {
        "mode": structured["mode"],
        "confidence": structured["confidence"],
        "sections": rendered,
        "sentences": structured["sentences"],
    }
    if "_fallback_reason" in structured:
        result["soap"]["_fallback_reason"] = structured["_fallback_reason"]
        warnings.append({
            "level": "info",
            "message": "LLM structuring unavailable; used the rule classifier instead.",
        })

    # --- Vitals ---------------------------------------------------------------
    vitals = _timed("vitals", medical.extract_vitals, transcript)
    result["vitals"] = vitals
    for vital in vitals:
        if not vital.get("plausible", True):
            warnings.append({
                "level": "high",
                "message": vital.get("warning", "Implausible vital sign value."),
            })

    # --- Medications ----------------------------------------------------------
    medications = _timed("medications", medical.correct_medications, transcript)
    result["medications"] = medications
    for entry in medications:
        if not entry["exact"]:
            # Every inexact match is surfaced. A LOW-confidence match is the case
            # that most needs a human look, so warning only on confident matches
            # would silence exactly the wrong half.
            top = entry["suggestions"][0]
            warnings.append({
                "level": "medium" if entry.get("confident") else "high",
                "message": (
                    'Heard "{0}"; closest formulary entry is "{1}" '
                    '(match {2:.0%}{3}). Confirm before saving.'.format(
                        entry["heard"], top["name"], top["score"],
                        ", weak" if not entry.get("confident") else "")
                ),
            })
            if top.get("lasa"):
                warnings.append({
                    "level": "high",
                    "message": '"{0}" has look-alike/sound-alike confusables: {1}.'.format(
                        top["name"], ", ".join(top["lasa"])),
                })

    # --- Abbreviations --------------------------------------------------------
    abbreviations = _timed("abbreviations", medical.expand_abbreviations, transcript)
    result["abbreviations"] = abbreviations
    for item in abbreviations:
        if "ismp_error_prone" in item:
            warnings.append({
                "level": "high",
                "message": '"{0}" is an ISMP error-prone abbreviation. {1}'.format(
                    item["abbreviation"], item["ismp_error_prone"]),
            })

    # --- Negation -------------------------------------------------------------
    vocabulary = _finding_vocabulary()
    present = [term for term in vocabulary if term in transcript.lower()]
    negation = _timed("negation", medical.detect_negation, transcript, present)
    result["negation"] = negation

    affirmed = {n["finding"] for n in negation if n["status"] == "affirmed"}
    negated = sorted({n["finding"] for n in negation if n["status"] == "negated"})
    uncertain = sorted({n["finding"] for n in negation if n["status"] == "uncertain"})
    result["findings"] = {
        "affirmed": sorted(affirmed),
        "negated": negated,
        "uncertain": uncertain,
    }

    # --- ICD-10 ---------------------------------------------------------------
    if suggest_icd:
        # Code from the assessment when one was dictated; otherwise the whole
        # note. Either way, drop text spans covering negated findings so a
        # ruled-out condition cannot become a suggested code.
        source = rendered.get("assessment") or transcript
        cleaned = source
        for term in negated:
            cleaned = cleaned.replace(term, " ").replace(term.title(), " ")

        mark = time.perf_counter()
        codes = coding.suggest_codes(cleaned, _MAX_CODES)

        # A single assessment sentence often carries more than one condition
        # ("viral URI with uncontrolled hypertension"). Ranking the sentence as
        # a whole surfaces only the dominant one, so each affirmed finding is
        # also coded on its own and the results are merged.
        per_finding: List[Dict[str, Any]] = []
        seen_codes = {c["code"] for c in codes}
        for finding in sorted(affirmed):
            best = coding.suggest_codes(finding, top_n=1)
            if not best:
                continue
            entry = dict(best[0])
            entry["finding"] = finding
            per_finding.append(entry)
            if entry["code"] not in seen_codes:
                seen_codes.add(entry["code"])
                promoted = dict(entry)
                promoted["rank"] = len(codes) + 1
                promoted["promoted_from_finding"] = finding
                codes.append(promoted)

        timings["icd10"] = round((time.perf_counter() - mark) * 1000, 2)
        result["icd10"] = {
            "candidates": codes,
            "per_finding": per_finding,
            "source_section": "assessment" if rendered.get("assessment") else "full_transcript",
            "excluded_negated_findings": negated,
            "disclaimer": coding.corpus_info()["disclaimer"],
        }

    # --- Field mappings -------------------------------------------------------
    entities: Dict[str, Dict[str, Any]] = {}

    for section, text in rendered.items():
        if text.strip():
            entities[section] = {
                "value": text.strip(),
                "confidence": structured["confidence"],
            }
    if rendered.get("subjective"):
        entities["chief_complaint"] = {
            "value": rendered["subjective"].strip(),
            "confidence": round(structured["confidence"] * 0.9, 3),
        }

    _VITAL_TO_ENTITY = {
        "heart_rate": "heart_rate",
        "respiratory_rate": "respiratory_rate",
        "oxygen_saturation": "oxygen_saturation",
        "temperature": "temperature",
        "weight": "weight",
    }
    for vital in vitals:
        confidence = 0.92 if vital.get("plausible", True) else 0.35
        if vital["type"] == "blood_pressure":
            entities["blood_pressure_systolic"] = {
                "value": vital["systolic"], "confidence": confidence}
            entities["blood_pressure_diastolic"] = {
                "value": vital["diastolic"], "confidence": confidence}
        elif vital["type"] in _VITAL_TO_ENTITY:
            entities[_VITAL_TO_ENTITY[vital["type"]]] = {
                "value": vital["value"], "confidence": confidence}

    if suggest_icd and result.get("icd10", {}).get("candidates"):
        best = result["icd10"]["candidates"][0]
        entities["diagnosis"] = {
            "value": "{0} - {1}".format(best["code"], best["description"]),
            "confidence": best["confidence"],
        }

    confident_meds = [
        entry["suggestions"][0]["name"]
        for entry in medications
        if entry["exact"] or entry.get("confident")
    ]
    if confident_meds:
        entities["medication"] = {
            "value": ", ".join(sorted(set(confident_meds))),
            "confidence": 0.80,
        }

    result["field_mappings"] = map_entities_to_fields(entities)
    result["warnings"] = warnings

    timings["total"] = round((time.perf_counter() - started) * 1000, 2)
    result["timings_ms"] = timings
    return result


def capabilities() -> Dict[str, Any]:
    """Describe which analysis layers are available in this deployment."""
    try:
        import spacy  # noqa: F401
        spacy_available = True
    except ImportError:
        spacy_available = False

    return {
        "layers": {
            "asr_quality": {
                "available": True,
                "kind": "statistical",
                "detail": "Whisper decoding statistics; no extra model.",
            },
            "soap_structuring": {
                "available": True,
                "kind": "rule-based (LLM optional)",
                "detail": "Cue-phrase scoring; Ollama path when use_llm=true.",
            },
            "medical_vocabulary": {
                "available": True,
                "kind": "rule-based + phonetic",
                "detail": "Soundex + edit distance over a {0}-entry formulary.".format(
                    len(medical._medications())),  # noqa: SLF001
            },
            "negation": {
                "available": True,
                "kind": "rule-based",
                "detail": "NegEx, sentence-scoped.",
            },
            "icd10_coding": {
                "available": True,
                "kind": "information retrieval",
                "detail": coding.corpus_info()["algorithm"],
            },
            "phi_detection": {
                "available": True,
                "kind": "pattern + NER" if spacy_available else "pattern (NER degraded)",
                "detail": (
                    "spaCy NER available."
                    if spacy_available else
                    "spaCy not installed; person/place detection uses the pattern fallback."
                ),
            },
            "entity_extraction": {
                "available": spacy_available,
                "kind": "statistical NER",
                "detail": (
                    "spaCy en_core_web_sm."
                    if spacy_available else
                    "Requires spaCy: pip install spacy && python -m spacy download en_core_web_sm"
                ),
            },
        },
        "icd10_corpus": coding.corpus_info(),
        "notes": [
            "Every layer returns suggestions for clinician confirmation.",
            "No layer writes to the chart on its own.",
        ],
    }
