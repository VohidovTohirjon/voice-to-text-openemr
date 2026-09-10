"""
Clinical Vocabulary Layer
=========================
Post-processing that turns a raw ASR transcript into clinically usable text.
Four independent passes, each of which can be used on its own:

  1. expand_abbreviations  — clinical shorthand -> full term (suggestions only)
  2. correct_medications   — phonetic + orthographic matching against a formulary
  3. extract_vitals        — vital signs with unit normalisation and range checks
  4. detect_negation       — NegEx-style assertion status for clinical findings

Why this layer exists
---------------------
Whisper is a general-purpose model. It transcribes conversational English well
but has three predictable failure modes on clinical dictation:

  * drug names are mis-heard ("lisinapril", "metroprolol")
  * numbers drift, producing physiologically impossible vitals
  * shorthand is transcribed phonetically ("sob", "q d")

None of those are fixable by a better decoder alone — they need domain
knowledge. This module supplies it with no additional model weights and no
network calls, so it runs anywhere the API runs.

Safety posture
--------------
Every function here RETURNS SUGGESTIONS. Nothing rewrites the transcript in
place. The caller decides what to surface, and the clinician confirms. A
medication correction that silently replaced a drug name would be a patient
safety defect, not a feature.
"""

from __future__ import annotations

import difflib
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

_abbrev_cache: Optional[Dict[str, Dict[str, Any]]] = None
_med_cache: Optional[List[Dict[str, Any]]] = None


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _load_json(filename: str) -> Dict[str, Any]:
    with open(os.path.join(_DATA_DIR, filename), "r", encoding="utf-8") as fh:
        return json.load(fh)


def _abbreviations() -> Dict[str, Dict[str, Any]]:
    """Flatten the grouped abbreviation file into one uppercase-keyed table."""
    global _abbrev_cache
    if _abbrev_cache is None:
        raw = _load_json("abbreviations.json")
        flat: Dict[str, Dict[str, Any]] = {}
        for group, entries in raw.items():
            if group.startswith("_"):
                continue
            for abbr, meta in entries.items():
                item = dict(meta)
                item["category"] = group
                flat[abbr.upper()] = item
        _abbrev_cache = flat
    return _abbrev_cache


def _medications() -> List[Dict[str, Any]]:
    global _med_cache
    if _med_cache is None:
        _med_cache = _load_json("medications.json")["medications"]
    return _med_cache


# ---------------------------------------------------------------------------
# 1. Abbreviation expansion
# ---------------------------------------------------------------------------

# Dictated shorthand often arrives letter-spaced ("q d", "b i d"). Collapse
# those before lookup so "b i d" and "bid" hit the same entry.
_SPACED_LETTERS = re.compile(r"\b(?:[a-z]\s){1,5}[a-z]\b", re.IGNORECASE)


def _despace_shorthand(text: str) -> str:
    def join(match: "re.Match") -> str:
        return match.group(0).replace(" ", "")

    return _SPACED_LETTERS.sub(join, text)


def expand_abbreviations(transcript: str) -> List[Dict[str, Any]]:
    """
    Find clinical abbreviations and propose expansions.

    Returns one record per occurrence:
        abbreviation, expansion, category, start, end,
        ambiguous       — list of competing readings, when the term has more than one
        ismp_error_prone — guidance string when the term is on the ISMP list
        confidence      — lower when the term is ambiguous
    """
    table = _abbreviations()
    normalised = _despace_shorthand(transcript)
    found: List[Dict[str, Any]] = []

    for abbr, meta in table.items():
        # N/V and F/U contain a slash; escape defensively for all keys.
        pattern = re.compile(r"(?<![A-Za-z0-9])" + re.escape(abbr) + r"(?![A-Za-z0-9])",
                             re.IGNORECASE)
        for match in pattern.finditer(normalised):
            ambiguous = meta.get("ambiguous")
            record: Dict[str, Any] = {
                "abbreviation": match.group(0),
                "expansion": meta["expansion"],
                "category": meta["category"],
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.60 if ambiguous else 0.90,
            }
            if ambiguous:
                record["ambiguous"] = ambiguous
            if "ismp_error_prone" in meta:
                record["ismp_error_prone"] = meta["ismp_error_prone"]
                record["confidence"] = min(record["confidence"], 0.55)
            found.append(record)

    found.sort(key=lambda item: item["start"])
    return found


# ---------------------------------------------------------------------------
# 2. Medication correction (phonetic + orthographic)
# ---------------------------------------------------------------------------


_soundex_cache: Dict[str, str] = {}


def soundex(word: str) -> str:
    """
    Classic Soundex. Cheap, and good at the vowel-substitution errors ASR makes
    ("lisinapril" / "lisinopril"). Used alongside an edit-distance score because
    Soundex alone is far too permissive on long drug names.
    """
    cached = _soundex_cache.get(word)
    if cached is not None:
        return cached
    original = word

    word = re.sub(r"[^A-Za-z]", "", word).upper()
    if not word:
        _soundex_cache[original] = ""
        return ""

    codes = {
        **{c: "1" for c in "BFPV"},
        **{c: "2" for c in "CGJKQSXZ"},
        **{c: "3" for c in "DT"},
        **{c: "4" for c in "L"},
        **{c: "5" for c in "MN"},
        **{c: "6" for c in "R"},
    }

    first = word[0]
    encoded = [codes.get(first, "")]
    for char in word[1:]:
        code = codes.get(char, "")
        # H and W are transparent: they do not break a run of like digits.
        if char in "HW":
            continue
        if code and code != encoded[-1]:
            encoded.append(code)
        elif not code:
            encoded.append("")

    digits = "".join(d for d in encoded[1:] if d)
    code = (first + digits + "000")[:4]
    _soundex_cache[original] = code
    return code


def _consonant_skeleton(word: str) -> str:
    """Vowel-stripped form. ASR errors cluster in vowels; consonants survive."""
    return re.sub(r"[^bcdfghjklmnpqrstvwxyz]", "", word.lower())


def _similarity(candidate: str, target: str) -> float:
    """Blend orthographic, phonetic and skeletal similarity into one score."""
    ortho = difflib.SequenceMatcher(None, candidate, target).ratio()
    # Graded, not binary: a transposition ("metroprolol") changes the Soundex
    # code without making the words phonetically unrelated, and an all-or-nothing
    # phonetic term would push those common ASR errors below threshold.
    phon = difflib.SequenceMatcher(None, soundex(candidate), soundex(target)).ratio()
    skel = difflib.SequenceMatcher(
        None, _consonant_skeleton(candidate), _consonant_skeleton(target)
    ).ratio()
    return 0.55 * ortho + 0.20 * phon + 0.25 * skel


# Words that look drug-like but are ordinary English; never propose a correction.
_STOPWORDS = {
    "patient", "reports", "reported", "denies", "history", "started", "stopped",
    "continue", "continues", "increase", "decrease", "daily", "twice", "three",
    "morning", "evening", "night", "tablet", "tablets", "capsule", "capsules",
    "milligram", "milligrams", "dose", "doses", "prescribed", "taking", "takes",
    "medication", "medications", "allergy", "allergies", "pressure", "blood",
    "chronic", "acute", "severe", "moderate", "follow", "review", "assessment",
    "examination", "complains", "presents", "current", "currently", "without",
}

_MIN_TOKEN_LEN = 5
_STRONG = 0.86   # accept as a confident correction
_WEAK = 0.72     # surface for review, do not lead with it


def _rank_candidates(
    surface: str,
    index: List[Tuple[str, Dict[str, Any]]],
    max_suggestions: int,
) -> List[Dict[str, Any]]:
    """Score one surface form against the formulary and return the best matches."""
    scored: Dict[str, Dict[str, Any]] = {}

    for name, entry in index:
        # Length guard keeps "reported" from being scored against every drug.
        if abs(len(name) - len(surface)) > 4:
            continue
        score = _similarity(surface, name)
        if score < _WEAK:
            continue
        keep = scored.get(entry["name"])
        if keep is None or score > keep["score"]:
            scored[entry["name"]] = {
                "name": entry["name"],
                "drug_class": entry["class"],
                "score": round(score, 3),
                "lasa": entry.get("lasa", []),
            }

    ranked = sorted(scored.values(), key=lambda s: s["score"], reverse=True)
    return ranked[:max_suggestions]


def correct_medications(transcript: str, max_suggestions: int = 3) -> List[Dict[str, Any]]:
    """
    Detect probable medication mentions and rank formulary matches.

    Two passes run over the text:

      unigram  each word on its own — catches the usual vowel and transposition
               errors ("lisinapril", "metroprolol").
      bigram   adjacent word pairs joined — catches names the decoder split in
               two ("lisin opril"). A bigram is only kept when it beats both of
               its constituent words, so ordinary word pairs do not compete with
               genuine single-word matches.

    Severely fragmented names ("acetaminophen" heard as "a seed of minifin")
    are NOT recoverable this way; the surface form no longer resembles the drug.
    That failure mode needs a domain-adapted acoustic model, not a better string
    metric, and is the concrete argument for evaluating a medical ASR model.

    Returns one record per suspicious span:
        heard, start, end, exact, needs_review, confident, suggestions, source
    """
    formulary = _medications()
    # Multi-word entries ("insulin glargine") are matched on their first word.
    index: List[Tuple[str, Dict[str, Any]]] = []
    for entry in formulary:
        index.append((entry["name"].lower(), entry))
        head = entry["name"].split()[0].lower()
        if head != entry["name"].lower():
            index.append((head, entry))

    exact_names = {name for name, _ in index}
    tokens = [(m.group(0), m.start(), m.end())
              for m in re.finditer(r"\b[A-Za-z][A-Za-z\-]{3,}\b", transcript)]

    results: List[Dict[str, Any]] = []
    unigram_best: Dict[int, float] = {}

    for position, (token, start, end) in enumerate(tokens):
        lowered = token.lower()

        if lowered in _STOPWORDS or len(lowered) < _MIN_TOKEN_LEN:
            continue

        if lowered in exact_names:
            entry = next(e for name, e in index if name == lowered)
            unigram_best[position] = 1.0
            results.append({
                "heard": token,
                "start": start,
                "end": end,
                "exact": True,
                "needs_review": False,
                "confident": True,
                "source": "unigram",
                "suggestions": [{
                    "name": entry["name"],
                    "drug_class": entry["class"],
                    "score": 1.0,
                    "lasa": entry.get("lasa", []),
                }],
            })
            continue

        ranked = _rank_candidates(lowered, index, max_suggestions)
        if not ranked:
            continue

        unigram_best[position] = ranked[0]["score"]
        results.append({
            "heard": token,
            "start": start,
            "end": end,
            "exact": False,
            "needs_review": True,
            "confident": ranked[0]["score"] >= _STRONG,
            "source": "unigram",
            "suggestions": ranked,
        })

    # Bigram pass: a name the decoder split across two words.
    for position in range(len(tokens) - 1):
        first, second = tokens[position], tokens[position + 1]
        # Only join words that are adjacent in the text, not across punctuation.
        between = transcript[first[2]:second[1]]
        if between.strip():
            continue

        joined = (first[0] + second[0]).lower()
        if len(joined) < 8:
            continue
        if first[0].lower() in _STOPWORDS or second[0].lower() in _STOPWORDS:
            continue

        if joined in exact_names:
            # The decoder split a real drug name in two. Rejoining recovers it
            # exactly, which is the strongest possible evidence.
            entry = next(e for name, e in index if name == joined)
            ranked = [{
                "name": entry["name"],
                "drug_class": entry["class"],
                "score": 1.0,
                "lasa": entry.get("lasa", []),
            }]
        else:
            ranked = _rank_candidates(joined, index, max_suggestions)
        if not ranked:
            continue

        # Keep only if the joined form beats both words taken separately.
        best_alone = max(unigram_best.get(position, 0.0),
                         unigram_best.get(position + 1, 0.0))
        if ranked[0]["score"] <= best_alone:
            continue

        results = [r for r in results
                   if not (r["start"] >= first[1] and r["end"] <= second[2])]
        results.append({
            "heard": transcript[first[1]:second[2]],
            "start": first[1],
            "end": second[2],
            "exact": False,
            "needs_review": True,
            "confident": ranked[0]["score"] >= _STRONG,
            "source": "bigram",
            "suggestions": ranked,
        })

    results.sort(key=lambda r: r["start"])
    return results


# ---------------------------------------------------------------------------
# 3. Vital signs
# ---------------------------------------------------------------------------
# Plausible-range bounds are deliberately wide: the goal is to catch transcription
# damage ("blood pressure 1 20 over 80" -> 120/80 vs 1/20), not to judge acuity.

_VITAL_RANGES = {
    "systolic_bp": (60, 260, "mmHg"),
    "diastolic_bp": (30, 160, "mmHg"),
    "heart_rate": (25, 220, "bpm"),
    "respiratory_rate": (6, 60, "breaths/min"),
    "temperature_c": (30.0, 43.0, "C"),
    "oxygen_saturation": (50, 100, "%"),
    "weight_kg": (2.0, 350.0, "kg"),
}

_BP = re.compile(
    r"(?:blood\s+pressure|bp)\D{0,12}(\d{1,3})\s*(?:/|over)\s*(\d{1,3})"
    r"|(?<![\d/])(\d{2,3})\s*(?:/|over)\s*(\d{2,3})(?![\d/])",
    re.IGNORECASE,
)
_HR = re.compile(r"(?:heart\s+rate|pulse|\bhr\b)\D{0,12}(\d{2,3})", re.IGNORECASE)
_RR = re.compile(r"(?:respiratory\s+rate|respirations|\brr\b)\D{0,12}(\d{1,2})", re.IGNORECASE)
_TEMP = re.compile(
    r"(?:temperature|temp|fever\s+of)\D{0,12}(\d{2,3}(?:\.\d)?)\s*"
    r"(?:degrees?\s*)?(celsius|centigrade|fahrenheit|[cf])?\b",
    re.IGNORECASE,
)
_SPO2 = re.compile(
    r"(?:oxygen\s+saturation|o2\s*sat(?:uration)?|spo2|sat(?:s)?)\D{0,12}(\d{2,3})\s*%?",
    re.IGNORECASE,
)
_WEIGHT = re.compile(
    r"(?:weight|weighs|weighing)\D{0,12}(\d{2,3}(?:\.\d)?)\s*"
    r"(kilograms?|kgs?|pounds?|lbs?|lb)\b",
    re.IGNORECASE,
)


def _range_check(name: str, value: float) -> Dict[str, Any]:
    low, high, unit = _VITAL_RANGES[name]
    ok = low <= value <= high
    out: Dict[str, Any] = {"unit": unit, "plausible": ok}
    if not ok:
        out["warning"] = (
            "Value {0} {1} is outside the plausible range {2}-{3}; "
            "likely a transcription error.".format(value, unit, low, high)
        )
    return out


def extract_vitals(transcript: str) -> List[Dict[str, Any]]:
    """
    Pull vital signs out of dictated text, normalise units, and range-check.

    Temperature is the interesting case: dictation rarely states the scale, so
    the scale is inferred from magnitude (roughly 95-108 is Fahrenheit, 35-42 is
    Celsius) and both values are returned.
    """
    vitals: List[Dict[str, Any]] = []

    for match in _BP.finditer(transcript):
        systolic, diastolic = (match.group(1), match.group(2))
        if systolic is None:
            systolic, diastolic = (match.group(3), match.group(4))
        sys_v, dia_v = int(systolic), int(diastolic)
        record: Dict[str, Any] = {
            "type": "blood_pressure",
            "value": "{0}/{1}".format(sys_v, dia_v),
            "systolic": sys_v,
            "diastolic": dia_v,
            "unit": "mmHg",
            "text": match.group(0).strip(),
            "start": match.start(),
            "end": match.end(),
        }
        sys_check = _range_check("systolic_bp", sys_v)
        dia_check = _range_check("diastolic_bp", dia_v)
        record["plausible"] = sys_check["plausible"] and dia_check["plausible"] and sys_v > dia_v
        if not record["plausible"]:
            record["warning"] = (
                sys_check.get("warning")
                or dia_check.get("warning")
                or "Systolic must exceed diastolic; likely a transcription error."
            )
        vitals.append(record)

    simple = [
        (_HR, "heart_rate", "heart_rate", int),
        (_RR, "respiratory_rate", "respiratory_rate", int),
        (_SPO2, "oxygen_saturation", "oxygen_saturation", int),
    ]
    for pattern, vital_type, range_key, cast in simple:
        for match in pattern.finditer(transcript):
            value = cast(match.group(1))
            check = _range_check(range_key, value)
            record = {
                "type": vital_type,
                "value": value,
                "unit": check["unit"],
                "plausible": check["plausible"],
                "text": match.group(0).strip(),
                "start": match.start(),
                "end": match.end(),
            }
            if "warning" in check:
                record["warning"] = check["warning"]
            vitals.append(record)

    for match in _TEMP.finditer(transcript):
        value = float(match.group(1))
        scale = (match.group(2) or "").lower()
        if scale.startswith("f") or (not scale and value >= 80):
            celsius = round((value - 32.0) * 5.0 / 9.0, 1)
            fahrenheit = value
            inferred = not scale
        else:
            celsius = value
            fahrenheit = round(value * 9.0 / 5.0 + 32.0, 1)
            inferred = not scale
        check = _range_check("temperature_c", celsius)
        record = {
            "type": "temperature",
            "value": celsius,
            "unit": "C",
            "value_fahrenheit": fahrenheit,
            "scale_inferred": inferred,
            "plausible": check["plausible"],
            "text": match.group(0).strip(),
            "start": match.start(),
            "end": match.end(),
        }
        if "warning" in check:
            record["warning"] = check["warning"]
        vitals.append(record)

    for match in _WEIGHT.finditer(transcript):
        value = float(match.group(1))
        unit = match.group(2).lower()
        kilograms = round(value * 0.45359237, 1) if unit.startswith(("p", "lb")) else value
        check = _range_check("weight_kg", kilograms)
        record = {
            "type": "weight",
            "value": kilograms,
            "unit": "kg",
            "as_dictated": "{0} {1}".format(value, unit),
            "plausible": check["plausible"],
            "text": match.group(0).strip(),
            "start": match.start(),
            "end": match.end(),
        }
        if "warning" in check:
            record["warning"] = check["warning"]
        vitals.append(record)

    vitals.sort(key=lambda v: v["start"])
    return vitals


# ---------------------------------------------------------------------------
# 4. Negation / assertion detection (NegEx)
# ---------------------------------------------------------------------------
# Implementation of the NegEx algorithm (Chapman et al., 2001): a trigger term
# negates findings within a bounded window unless a termination term closes the
# scope first. Roughly 80% of negations in clinical text are simple enough for
# this to handle, which is why it remains the baseline in clinical NLP.

_PSEUDO_NEGATION = [
    "no increase", "no change", "not able to", "no further", "not only",
    "no significant change", "gram negative", "no suspicious",
]
_PRE_NEGATION = [
    "denies", "denied", "no evidence of", "no sign of", "no signs of",
    "not complaining of", "negative for", "without", "absent", "free of",
    "rules out", "ruled out", "no", "not", "never had", "declines",
]
_POST_NEGATION = [
    "was ruled out", "is ruled out", "were ruled out", "is negative",
    "was negative", "are negative", "not seen", "is absent",
]
_TERMINATION = [
    "but", "however", "although", "though", "except", "aside from",
    "apart from", "yet", "still", "nevertheless", "reports", "complains of",
    "positive for", "presents with", "admits to",
]
_UNCERTAIN = [
    "possible", "possibly", "probable", "probably", "likely", "unlikely",
    "may have", "might have", "suspected", "suspicion for", "cannot rule out",
    "concerning for", "questionable", "rule out",
]

_SCOPE_TOKENS = 6


def _tokenise(text: str) -> List[Tuple[str, int, int]]:
    return [(m.group(0).lower(), m.start(), m.end())
            for m in re.finditer(r"[A-Za-z0-9']+", text)]


def _sentence_ids(text: str, tokens: List[Tuple[str, int, int]]) -> List[int]:
    """
    Map each token to the index of the sentence containing it.

    NegEx scope is sentence-bounded. Without this, "reports headache. Fever was
    ruled out." lets the post-trigger reach backwards across the full stop and
    negate the headache.
    """
    boundaries = [m.start() for m in re.finditer(r"[.;!?]", text)]
    ids: List[int] = []
    for _word, start, _end in tokens:
        ids.append(sum(1 for b in boundaries if b < start))
    return ids


def _phrase_positions(tokens: List[Tuple[str, int, int]], phrases: List[str]) -> List[Tuple[int, int, str]]:
    """Return (start_index, end_index, phrase) for each phrase occurrence."""
    words = [t[0] for t in tokens]
    hits: List[Tuple[int, int, str]] = []
    for phrase in phrases:
        parts = phrase.split()
        span = len(parts)
        for i in range(len(words) - span + 1):
            if words[i:i + span] == parts:
                hits.append((i, i + span, phrase))
    return hits


def detect_negation(transcript: str, findings: List[str]) -> List[Dict[str, Any]]:
    """
    Assign an assertion status to each clinical finding mentioned in the text.

    Args:
        transcript: the note text.
        findings:   clinical terms to check, e.g. ["chest pain", "fever"].

    Returns one record per located finding:
        finding, status (affirmed | negated | uncertain), trigger, start, end
    """
    tokens = _tokenise(transcript)
    words = [t[0] for t in tokens]
    if not tokens:
        return []
    sentence_of = _sentence_ids(transcript, tokens)

    pseudo = _phrase_positions(tokens, _PSEUDO_NEGATION)
    pseudo_spans = {i for start, end, _ in pseudo for i in range(start, end)}

    pre = [h for h in _phrase_positions(tokens, _PRE_NEGATION) if h[0] not in pseudo_spans]
    post = _phrase_positions(tokens, _POST_NEGATION)
    uncertain = _phrase_positions(tokens, _UNCERTAIN)
    terminators = _phrase_positions(tokens, _TERMINATION)
    terminator_starts = {start for start, _, _ in terminators}

    results: List[Dict[str, Any]] = []

    for finding in findings:
        parts = finding.lower().split()
        span = len(parts)
        for i in range(len(words) - span + 1):
            if words[i:i + span] != parts:
                continue

            status, trigger = "affirmed", None

            # Pre-trigger: scan forward from the trigger to the finding.
            for tstart, tend, phrase in pre:
                if not (tend <= i < tend + _SCOPE_TOKENS):
                    continue
                if sentence_of[tstart] != sentence_of[i]:
                    continue
                # A termination term between trigger and finding closes the scope.
                if any(t in terminator_starts for t in range(tend, i)):
                    continue
                status, trigger = "negated", phrase
                break

            # Post-trigger: finding first, trigger just after.
            if status == "affirmed":
                for tstart, _tend, phrase in post:
                    if not (i + span <= tstart < i + span + _SCOPE_TOKENS):
                        continue
                    if sentence_of[tstart] != sentence_of[i]:
                        continue
                    status, trigger = "negated", phrase
                    break

            if status == "affirmed":
                for tstart, tend, phrase in uncertain:
                    if not (tend <= i < tend + _SCOPE_TOKENS):
                        continue
                    if sentence_of[tstart] != sentence_of[i]:
                        continue
                    if any(t in terminator_starts for t in range(tend, i)):
                        continue
                    status, trigger = "uncertain", phrase
                    break

            results.append({
                "finding": finding,
                "status": status,
                "trigger": trigger,
                "start": tokens[i][1],
                "end": tokens[i + span - 1][2],
            })

    results.sort(key=lambda r: r["start"])
    return results
