"""
SOAP Note Structuring
=====================
Turns a free-form dictated encounter into the four sections a clinical note is
organised around: Subjective, Objective, Assessment, Plan.

Two paths, same output shape:

  classify_soap_rules  cue-phrase scoring over sentences. Deterministic, no
                       dependencies, sub-millisecond, and every decision is
                       explainable by the cues that fired.

  classify_soap_llm    a local Llama model via Ollama, for dictation that is
                       conversational enough that cue phrases miss.

`structure_note` runs the rule path by default and can fall back from the LLM
path when Ollama is not running.

How the rule classifier works
-----------------------------
Two modes, because real dictation comes in two shapes.

  Header mode  — the clinician dictates "Objective:" or just "O:". An explicit
                 header is authoritative: every following sentence belongs to
                 that section until the next header. No scoring is attempted,
                 and confidence is 1.0.

  Scoring mode — no headers. Each sentence is scored against weighted cue sets
                 for the four sections; the winner is the argmax, and
                 confidence comes from the margin over the runner-up. A
                 sentence that scores nothing is assigned by position, since
                 dictation overwhelmingly runs S -> O -> A -> P in order.

The margin matters more than the raw score: "continue lisinopril" is
unambiguously Plan, while "patient is febrile" reads as both Subjective and
Objective, and the UI should show that it was a close call.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

SECTIONS = ("subjective", "objective", "assessment", "plan")

# Explicit dictated headers. Single letters are matched only when followed by a
# colon, so "A 45 year old" is not read as an Assessment header.
_HEADERS: List[Tuple[str, "re.Pattern"]] = [
    ("subjective", re.compile(r"^\s*(?:subjective|hpi|history of present illness|s)\s*[:\-]\s*", re.IGNORECASE)),
    ("objective", re.compile(r"^\s*(?:objective|physical exam(?:ination)?|exam|vitals?|o)\s*[:\-]\s*", re.IGNORECASE)),
    ("assessment", re.compile(r"^\s*(?:assessment|impression|diagnosis|dx|a)\s*[:\-]\s*", re.IGNORECASE)),
    ("plan", re.compile(r"^\s*(?:plan|treatment plan|management|disposition|p)\s*[:\-]\s*", re.IGNORECASE)),
]

# (phrase, weight). Weights are ordinal, not probabilities: a strong cue should
# outrank two weak ones.
_CUES: Dict[str, List[Tuple[str, float]]] = {
    "subjective": [
        ("complains of", 3.0), ("complaining of", 3.0), ("c/o", 3.0),
        ("reports", 2.5), ("reported", 2.5), ("denies", 2.5), ("denied", 2.5),
        ("states", 2.0), ("describes", 2.0), ("says", 2.0), ("tells me", 2.0),
        ("presents with", 2.5), ("presenting with", 2.5),
        ("history of present illness", 3.0), ("past medical history", 2.5),
        ("family history", 2.0), ("social history", 2.0),
        ("started", 1.2), ("began", 1.2), ("for the past", 1.5),
        ("worse", 1.0), ("better", 1.0), ("since", 0.8),
        ("no known drug allergies", 2.0), ("patient feels", 2.5),
    ],
    "objective": [
        ("on examination", 3.0), ("on exam", 3.0), ("physical exam", 3.0),
        ("auscultation", 2.5), ("palpation", 2.5), ("percussion", 2.0),
        ("blood pressure", 2.5), ("heart rate", 2.5), ("respiratory rate", 2.5),
        ("temperature", 2.0), ("oxygen saturation", 2.5), ("vital signs", 3.0),
        ("appears", 2.0), ("alert and oriented", 2.5), ("no acute distress", 2.5),
        ("within normal limits", 2.5), ("unremarkable", 2.0),
        ("regular rate and rhythm", 2.5), ("clear to auscultation", 2.5),
        ("laboratory", 2.0), ("labs", 2.0), ("x-ray", 2.0), ("imaging", 2.0),
        ("ecg", 2.0), ("ekg", 2.0), ("tender", 1.5), ("non-tender", 1.5),
        ("no edema", 1.5), ("weight", 1.2), ("bmi", 1.5),
    ],
    "assessment": [
        ("assessment", 3.0), ("impression", 3.0), ("diagnosis", 3.0),
        ("differential", 2.5), ("consistent with", 2.5), ("likely", 2.0),
        ("suspect", 2.0), ("suspected", 2.0), ("probable", 2.0),
        ("rule out", 2.0), ("cannot rule out", 2.0), ("secondary to", 1.8),
        ("stable", 1.5), ("uncontrolled", 1.8), ("well controlled", 1.8),
        ("improving", 1.5), ("worsening", 1.5), ("acute", 1.0), ("chronic", 1.0),
    ],
    "plan": [
        ("plan", 3.0), ("will start", 3.0), ("start", 2.2), ("initiate", 2.5),
        ("continue", 2.5), ("discontinue", 2.5), ("stop", 2.0), ("hold", 1.8),
        ("increase", 2.0), ("decrease", 2.0), ("titrate", 2.5),
        ("prescribe", 3.0), ("prescribed", 2.5), ("refill", 2.5),
        ("refer", 3.0), ("referral", 3.0), ("follow up", 3.0), ("follow-up", 3.0),
        ("return in", 3.0), ("return to clinic", 3.0), ("recheck", 2.5),
        ("order", 2.0), ("ordered", 2.0), ("obtain", 2.0), ("check", 1.8),
        ("recommend", 2.5), ("advised", 2.5), ("counseled", 2.5),
        ("educated", 2.0), ("instructed", 2.0), ("encouraged", 1.8),
        ("as needed", 1.5), ("daily", 1.0), ("twice daily", 1.5),
    ],
}

# Dictation runs S -> O -> A -> P far more often than not, so an uninformative
# sentence inherits the section its neighbours established.
_DEFAULT_ORDER = list(SECTIONS)


# Abbreviations whose trailing period is not a sentence end.
_ABBREVIATIONS = {
    "dr", "mr", "mrs", "ms", "prof", "jr", "sr", "st", "vs", "approx", "etc",
    "no", "mg", "mcg", "ml", "dl", "kg", "lb", "oz", "hr", "min", "wk", "yr",
    "am", "pm", "inc", "dept", "est",
}

# A sentence ends at terminal punctuation followed by whitespace or end of text,
# or at a line break. Requiring the whitespace is what keeps "38.0 degrees" and
# "37.8," intact: a decimal point has a digit after it, never a space.
_BOUNDARY = re.compile(r"[.!?]+(?=\s|$)|\n+")

# Phrases that open a new clinical section. Whisper frequently transcribes a
# dictated pause as a comma rather than a full stop, which glues a whole note
# into one "sentence" and leaves Assessment and Plan empty. Splitting at a comma
# that is immediately followed by one of these is what recovers the structure.
_SECTION_OPENERS = (
    "impression is", "impression", "assessment is", "assessment",
    "diagnosis is", "diagnosis",
    "plan is", "plan", "we will", "follow up", "return in", "recheck",
    "on examination", "on exam", "physical exam",
    "temperature", "blood pressure", "pulse", "heart rate",
    "respiratory rate", "oxygen saturation", "o2 sat", "weight",
    "patient reports", "patient denies", "she denies", "he denies",
    "she reports", "he reports", "no known",
)
_CLAUSE_BOUNDARY = re.compile(
    r",\s+(?=(?:" + "|".join(re.escape(p) for p in _SECTION_OPENERS) + r")\b)",
    re.IGNORECASE,
)


def split_sentences(text: str) -> List[Dict[str, Any]]:
    """
    Sentence splitter tuned for dictation.

    Splits on terminal punctuation and on line breaks, because dictated notes
    are frequently punctuation-free but line-broken. Two things that look like
    sentence ends are deliberately not treated as one:

      * the decimal point in a measurement ("temperature 38.0 degrees")
      * the period in an abbreviation ("Dr. Whitfield", "250 mg. daily")

    Splitting on either produces fragments that then get classified into the
    wrong SOAP section, which is why they are handled here rather than patched
    up downstream.
    """
    if not text or not text.strip():
        return []

    sentences: List[Dict[str, Any]] = []
    cursor = 0

    boundaries = sorted(
        [m for m in _BOUNDARY.finditer(text)] + [m for m in _CLAUSE_BOUNDARY.finditer(text)],
        key=lambda m: m.start(),
    )

    for match in boundaries:
        if match.start() < cursor:
            continue
        if match.group(0)[0] == ".":
            preceding = re.search(r"([A-Za-z]+)\.?$", text[cursor:match.start()])
            if preceding and preceding.group(1).lower() in _ABBREVIATIONS:
                continue

        chunk = text[cursor:match.end()]
        stripped = chunk.strip()
        if stripped:
            offset = cursor + (len(chunk) - len(chunk.lstrip()))
            sentences.append({
                "text": stripped,
                "start": offset,
                "end": offset + len(stripped),
            })
        cursor = match.end()

    remainder = text[cursor:]
    if remainder.strip():
        offset = cursor + (len(remainder) - len(remainder.lstrip()))
        stripped = remainder.strip()
        sentences.append({
            "text": stripped,
            "start": offset,
            "end": offset + len(stripped),
        })

    return sentences


def _score_sentence(sentence: str) -> Dict[str, float]:
    lowered = " " + re.sub(r"\s+", " ", sentence.lower()) + " "
    scores = {section: 0.0 for section in SECTIONS}

    for section, cues in _CUES.items():
        for phrase, weight in cues:
            if phrase in lowered:
                scores[section] += weight

    # A bare number pattern (140/90, 98.6, 72 bpm) is Objective evidence even
    # with no cue phrase present.
    if re.search(r"\b\d{2,3}\s*(?:/|over)\s*\d{2,3}\b", lowered):
        scores["objective"] += 2.5
    elif re.search(r"\b\d{2,3}(?:\.\d)?\s*(?:bpm|mmhg|%|degrees|kg|lbs?)\b", lowered):
        scores["objective"] += 2.0

    # Dose strings ("10 mg", "250 milligrams") are Plan evidence.
    if re.search(r"\b\d+\s*(?:mg|mcg|ml|milligrams?|micrograms?|units?)\b", lowered):
        scores["plan"] += 1.5

    return scores


def classify_soap_rules(transcript: str) -> Dict[str, Any]:
    """
    Assign each sentence to a SOAP section using cue scoring and headers.

    Returns:
        sections    — {section: [sentence records]}
        sentences   — flat list with section, confidence, method, cues
        mode        — "header" when explicit headers were dictated, else "scored"
        confidence  — mean sentence confidence
    """
    sentences = split_sentences(transcript)
    if not sentences:
        return {
            "sections": {s: [] for s in SECTIONS},
            "sentences": [],
            "mode": "empty",
            "confidence": 0.0,
        }

    # Pass 1: does this note use explicit headers?
    header_positions: List[Tuple[int, str, str]] = []
    for index, sentence in enumerate(sentences):
        for section, pattern in _HEADERS:
            match = pattern.match(sentence["text"])
            if match:
                remainder = sentence["text"][match.end():].strip()
                header_positions.append((index, section, remainder))
                break

    classified: List[Dict[str, Any]] = []
    mode = "header" if header_positions else "scored"

    if mode == "header":
        header_map = {index: (section, remainder)
                      for index, section, remainder in header_positions}
        current = header_positions[0][1]
        for index, sentence in enumerate(sentences):
            if index in header_map:
                current, remainder = header_map[index]
                body = remainder or sentence["text"]
                if not remainder:
                    continue  # header line with no content of its own
            else:
                body = sentence["text"]
            classified.append({
                "text": body,
                "section": current,
                "confidence": 1.0,
                "method": "explicit_header",
                "cues": [],
                "start": sentence["start"],
                "end": sentence["end"],
            })
    else:
        previous_section = None
        for position, sentence in enumerate(sentences):
            scores = _score_sentence(sentence["text"])
            ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
            best_section, best_score = ranked[0]
            runner_up = ranked[1][1]

            if best_score <= 0:
                # Nothing fired: follow the neighbour, else fall back to the
                # canonical S -> O -> A -> P position.
                fallback_index = min(
                    int(position * len(_DEFAULT_ORDER) / max(1, len(sentences))),
                    len(_DEFAULT_ORDER) - 1,
                )
                best_section = previous_section or _DEFAULT_ORDER[fallback_index]
                confidence = 0.30
                method = "positional_fallback"
                fired: List[str] = []
            else:
                margin = (best_score - runner_up) / best_score
                confidence = round(min(0.98, 0.45 + 0.5 * margin), 3)
                method = "cue_scoring"
                lowered = " " + sentence["text"].lower() + " "
                fired = [phrase for phrase, _w in _CUES[best_section]
                         if phrase in lowered]

            previous_section = best_section
            classified.append({
                "text": sentence["text"],
                "section": best_section,
                "confidence": confidence,
                "method": method,
                "cues": fired,
                "scores": {k: round(v, 2) for k, v in scores.items()},
                "start": sentence["start"],
                "end": sentence["end"],
            })

    grouped: Dict[str, List[Dict[str, Any]]] = {s: [] for s in SECTIONS}
    for item in classified:
        grouped[item["section"]].append(item)

    mean_confidence = (
        sum(c["confidence"] for c in classified) / len(classified)
        if classified else 0.0
    )

    return {
        "sections": grouped,
        "sentences": classified,
        "mode": mode,
        "confidence": round(mean_confidence, 3),
    }


def classify_soap_llm(transcript: str, model: str = "llama3.2:3b") -> Dict[str, Any]:
    """
    Structure the note with a local Llama model through Ollama.

    Raises on any failure so the caller can decide whether to fall back; it
    never returns a partial result that could be mistaken for a successful one.
    """
    import requests  # optional dependency

    prompt = (
        "You are structuring a clinical encounter note. Split the transcript "
        "into SOAP sections and return ONLY a JSON object with the keys "
        "\"subjective\", \"objective\", \"assessment\", \"plan\". Each value is "
        "a string containing the sentences belonging to that section, or an "
        "empty string. Do not invent content that is not in the transcript.\n\n"
        "Transcript: " + transcript + "\n\nJSON:"
    )

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=45,
    )
    response.raise_for_status()

    raw = response.json().get("response", "")
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("No JSON object in LLM response: {0!r}".format(raw[:200]))

    parsed = json.loads(match.group(0))

    grouped: Dict[str, List[Dict[str, Any]]] = {s: [] for s in SECTIONS}
    flat: List[Dict[str, Any]] = []
    for section in SECTIONS:
        body = (parsed.get(section) or "").strip()
        if not body:
            continue
        for sentence in split_sentences(body):
            record = {
                "text": sentence["text"],
                "section": section,
                "confidence": 0.75,
                "method": "llm",
                "cues": [],
                "start": sentence["start"],
                "end": sentence["end"],
            }
            grouped[section].append(record)
            flat.append(record)

    return {
        "sections": grouped,
        "sentences": flat,
        "mode": "llm",
        "confidence": 0.75,
        "model": model,
    }


def structure_note(transcript: str, use_llm: bool = False) -> Dict[str, Any]:
    """
    Structure a transcript into SOAP sections.

    With use_llm=True the Ollama path runs first and falls back to the rule
    classifier on any failure, reporting the reason in `_fallback_reason`.
    """
    if use_llm:
        try:
            return classify_soap_llm(transcript)
        except Exception as exc:  # noqa: BLE001 - fallback must be total
            result = classify_soap_rules(transcript)
            result["_fallback_reason"] = "{0}: {1}".format(type(exc).__name__, exc)
            return result

    return classify_soap_rules(transcript)


def render_sections(structured: Dict[str, Any]) -> Dict[str, str]:
    """Flatten the structure into one text block per section, ready for a form."""
    return {
        section: " ".join(item["text"] for item in structured["sections"].get(section, []))
        for section in SECTIONS
    }
