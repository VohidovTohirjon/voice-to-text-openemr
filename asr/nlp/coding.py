"""
ICD-10-CM Code Suggestion
=========================
Ranks diagnosis codes against dictated assessment text using Okapi BM25 — the
ranking function behind Lucene/Elasticsearch — implemented here in plain Python
so the service carries no search-engine dependency.

Why BM25 rather than embeddings
-------------------------------
Diagnosis text is short, and the vocabulary is closed and highly specific
("epigastric", "cerumen", "podagra"). Lexical ranking with IDF weighting beats
a general-purpose sentence embedding on exactly this shape of problem, needs no
model download, returns in microseconds, and — importantly for a clinical tool —
is fully explainable: every suggestion can show which query terms matched.

Scoring
-------
  IDF(q)   = ln(1 + (N - df + 0.5) / (df + 0.5))
  score(D) = sum over q of IDF(q) * f(q,D)*(k1+1)
                            / (f(q,D) + k1*(1 - b + b*|D|/avgdl))

with k1=1.5, b=0.75. A phrase bonus is added when a multi-word synonym appears
verbatim, because "chest pain" matching as a phrase is far stronger evidence
than "chest" and "pain" matching independently.

Safety posture
--------------
Output is a ranked candidate list for clinician selection. Codes are never
auto-applied. The bundled corpus is a curated primary-care demo subset, not a
licensed ICD-10-CM release.
"""

from __future__ import annotations

import json
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

K1 = 1.5
B = 0.75

# Half-saturation constant for absolute evidence. A raw BM25 score of this size
# maps to a strength of 0.5; tuned against the bundled corpus so a solid
# single-condition match lands near 0.85 and incidental matches stay low.
SATURATION = 5.0

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "has",
    "have", "in", "is", "it", "its", "of", "on", "or", "that", "the", "to", "was",
    "were", "will", "with", "without", "patient", "patients", "unspecified",
    "other", "due", "not", "no", "his", "her", "their", "this", "these", "also",
    # Generic English that leaks in through synonym phrasing such as
    # "flu like illness" and would otherwise let unrelated prose score.
    "like", "today", "yesterday", "tomorrow", "day", "week", "month", "year",
    "time", "ago", "still", "much", "many", "well", "good", "bad", "nice",
    "get", "got", "going", "want", "know", "think", "say", "make", "take",
}

_index_cache: Optional[Dict[str, Any]] = None


def _stem(word: str) -> str:
    """
    Deliberately small suffix stripper. Full Porter stemming over-conflates
    clinical terms (for example "coding"/"code"); this handles only the plural
    and participle endings that actually differ between dictation and the code
    descriptions.
    """
    for suffix in ("iness", "ing", "ies", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            if suffix == "ies":
                return word[: -len(suffix)] + "y"
            return word[: -len(suffix)]
    return word


def _tokenise(text: str) -> List[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [_stem(w) for w in words if w not in _STOPWORDS and len(w) > 1]


def _build_index() -> Dict[str, Any]:
    """Build the BM25 index once, at first use."""
    global _index_cache
    if _index_cache is not None:
        return _index_cache

    with open(os.path.join(_DATA_DIR, "icd10_subset.json"), "r", encoding="utf-8") as fh:
        raw = json.load(fh)

    documents: List[Dict[str, Any]] = []
    doc_freq: Dict[str, int] = {}

    for entry in raw["codes"]:
        synonyms = entry.get("syn", [])
        surface = entry["desc"] + " " + " ".join(synonyms)
        tokens = _tokenise(surface)

        frequencies: Dict[str, int] = {}
        for token in tokens:
            frequencies[token] = frequencies.get(token, 0) + 1
        for token in frequencies:
            doc_freq[token] = doc_freq.get(token, 0) + 1

        documents.append({
            "code": entry["code"],
            "desc": entry["desc"],
            "synonyms": synonyms,
            "tf": frequencies,
            "length": len(tokens),
            # Phrases kept in raw form for the verbatim-match bonus.
            "phrases": [s.lower() for s in synonyms if " " in s] + [entry["desc"].lower()],
        })

    total = len(documents)
    avg_length = sum(d["length"] for d in documents) / float(total) if total else 0.0

    idf = {
        token: math.log(1.0 + (total - df + 0.5) / (df + 0.5))
        for token, df in doc_freq.items()
    }

    _index_cache = {
        "documents": documents,
        "idf": idf,
        "avg_length": avg_length,
        "total": total,
        "release_note": raw.get("_meta", {}).get("release_note", ""),
    }
    return _index_cache


def suggest_codes(
    text: str,
    top_n: int = 5,
    min_score: float = 2.5,
) -> List[Dict[str, Any]]:
    """
    Rank ICD-10-CM candidates for a piece of assessment text.

    Args:
        text:      dictated assessment / diagnosis text.
        top_n:     maximum candidates returned.
        min_score: BM25 floor; below this the match is noise.

    Returns ranked records:
        code, description, score, confidence, matched_terms,
        phrase_match, needs_review
    """
    if not text or not text.strip():
        return []

    index = _build_index()
    query_tokens = _tokenise(text)
    if not query_tokens:
        return []

    lowered = " " + re.sub(r"\s+", " ", text.lower()) + " "
    results: List[Dict[str, Any]] = []

    for doc in index["documents"]:
        score = 0.0
        matched: List[str] = []

        for token in set(query_tokens):
            frequency = doc["tf"].get(token, 0)
            if not frequency:
                continue
            idf = index["idf"].get(token, 0.0)
            denominator = frequency + K1 * (
                1 - B + B * doc["length"] / (index["avg_length"] or 1.0)
            )
            score += idf * (frequency * (K1 + 1)) / denominator
            matched.append(token)

        if score <= 0:
            continue

        # Verbatim phrase evidence is worth more than the sum of its tokens.
        phrase_match = None
        for phrase in doc["phrases"]:
            if len(phrase) > 6 and (" " + phrase + " ") in lowered:
                phrase_match = phrase
                score *= 1.6
                break

        results.append({
            "code": doc["code"],
            "description": doc["desc"],
            "score": round(score, 3),
            "matched_terms": sorted(matched),
            "phrase_match": phrase_match,
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    results = [r for r in results if r["score"] >= min_score][:top_n]

    if not results:
        return []

    # Confidence combines three things, because any one alone misleads:
    #
    #   strength    absolute evidence, saturating. Without it, a query with one
    #               weak accidental match scores 1.0 simply for being top-ranked.
    #   share       this candidate's score relative to the best one.
    #   separation  how cleanly the best beats the runner-up. A narrow gap means
    #               "ambiguous", and the UI should show both rather than pick one.
    best = results[0]["score"]
    runner_up = results[1]["score"] if len(results) > 1 else 0.0
    separation = (best - runner_up) / best if best else 0.0
    strength = best / (best + SATURATION)

    for rank, item in enumerate(results):
        share = item["score"] / best if best else 0.0
        confidence = strength * share * (0.65 + 0.35 * separation)
        if item["phrase_match"]:
            confidence = min(1.0, confidence + 0.10)
        item["confidence"] = round(min(1.0, confidence), 3)
        item["rank"] = rank + 1
        item["needs_review"] = item["confidence"] < 0.75

    return results


def corpus_info() -> Dict[str, Any]:
    """Describe the bundled corpus, for the API's /capabilities response."""
    index = _build_index()
    return {
        "code_count": index["total"],
        "avg_document_length": round(index["avg_length"], 2),
        "vocabulary_size": len(index["idf"]),
        "algorithm": "Okapi BM25 (k1={0}, b={1}) with verbatim-phrase boost".format(K1, B),
        "release_note": index["release_note"],
        "disclaimer": (
            "Curated primary-care demo subset. Not a licensed ICD-10-CM release; "
            "validate against the current CMS/CDC files before billing use."
        ),
    }
