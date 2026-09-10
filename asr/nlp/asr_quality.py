"""
ASR Quality & Hallucination Detection
=====================================
Whisper already computes per-segment decoding statistics and then throws them
away: `transcribe()` returns them on each segment, and most integrations render
only `text`. This module reads those statistics and turns them into a
review signal the clinician can act on.

Signals used (all produced by Whisper itself, no second model):

  avg_logprob        mean log-probability of the tokens in the segment.
                     exp(avg_logprob) is the geometric-mean token probability,
                     which is the standard confidence proxy for seq2seq ASR.

  compression_ratio  len(text) / len(zlib(text)). Degenerate, looping output
                     compresses far better than natural speech, so a high ratio
                     is the classic repetition-hallucination signature.

  no_speech_prob     probability the segment is silence. Whisper is known to
                     emit fluent text over silence — training-data artefacts
                     such as subtitle credits. High no_speech_prob together
                     with a confident-looking transcript is the tell.

The thresholds below are Whisper's own decoding fallback thresholds
(compression_ratio_threshold=2.4, logprob_threshold=-1.0,
no_speech_threshold=0.6), reused here as review thresholds rather than as
re-decode triggers.

Clinical relevance: a hallucinated sentence in a chart note is worse than a
missing one, because it reads as fact. This module exists so that risk is
visible in the UI instead of silent.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional

# Whisper's own decoding fallback thresholds.
COMPRESSION_RATIO_THRESHOLD = 2.4
LOGPROB_THRESHOLD = -1.0
NO_SPEECH_THRESHOLD = 0.6

# Confidence below this is surfaced as "verify this span".
REVIEW_CONFIDENCE = 0.60


def segment_confidence(avg_logprob: Optional[float]) -> float:
    """
    Convert a mean token log-probability into a 0-1 confidence.

    exp(avg_logprob) is the geometric mean of the per-token probabilities.
    Values are clamped because temperature fallback can produce log-probs
    slightly above 0.
    """
    if avg_logprob is None:
        return 0.0
    try:
        return max(0.0, min(1.0, math.exp(float(avg_logprob))))
    except (OverflowError, ValueError):
        return 0.0


def _repeated_ngram(text: str, size: int = 4, times: int = 3) -> Optional[str]:
    """Return an n-gram repeated `times`+ in the segment, if any."""
    words = re.findall(r"[A-Za-z']+", text.lower())
    if len(words) < size * times:
        return None
    counts: Dict[str, int] = {}
    for i in range(len(words) - size + 1):
        gram = " ".join(words[i:i + size])
        counts[gram] = counts.get(gram, 0) + 1
        if counts[gram] >= times:
            return gram
    return None


def analyze_segments(segments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Score Whisper segments and flag the ones a clinician should re-listen to.

    Args:
        segments: the `segments` list from whisper's transcribe() result.

    Returns:
        overall_confidence — duration-weighted mean confidence
        segments           — per-segment scores and flags
        flagged            — subset needing review
        hallucination_risk — none | low | medium | high
        summary            — counts for the UI
    """
    scored: List[Dict[str, Any]] = []
    total_duration = 0.0
    weighted_confidence = 0.0

    for index, seg in enumerate(segments or []):
        text = (seg.get("text") or "").strip()
        start = float(seg.get("start", 0.0) or 0.0)
        end = float(seg.get("end", 0.0) or 0.0)
        duration = max(0.0, end - start)

        avg_logprob = seg.get("avg_logprob")
        compression = seg.get("compression_ratio")
        no_speech = seg.get("no_speech_prob")

        confidence = segment_confidence(avg_logprob)
        reasons: List[str] = []

        if avg_logprob is not None and float(avg_logprob) < LOGPROB_THRESHOLD:
            reasons.append(
                "low decoder confidence (avg_logprob {0:.2f} < {1})".format(
                    float(avg_logprob), LOGPROB_THRESHOLD)
            )
        if compression is not None and float(compression) > COMPRESSION_RATIO_THRESHOLD:
            reasons.append(
                "repetitive output (compression_ratio {0:.2f} > {1})".format(
                    float(compression), COMPRESSION_RATIO_THRESHOLD)
            )
        if no_speech is not None and float(no_speech) > NO_SPEECH_THRESHOLD:
            reasons.append(
                "probably silence (no_speech_prob {0:.2f} > {1})".format(
                    float(no_speech), NO_SPEECH_THRESHOLD)
            )

        gram = _repeated_ngram(text)
        if gram:
            reasons.append('phrase repeated three or more times ("{0}")'.format(gram))

        # Fluent-looking text over probable silence is the hallucination pattern
        # that most often survives into a note, so it is called out by name.
        hallucination = bool(
            gram
            or (compression is not None and float(compression) > COMPRESSION_RATIO_THRESHOLD)
            or (no_speech is not None and float(no_speech) > NO_SPEECH_THRESHOLD
                and confidence > 0.5 and len(text) > 20)
        )

        record = {
            "index": index,
            "text": text,
            "start": round(start, 2),
            "end": round(end, 2),
            "confidence": round(confidence, 3),
            "avg_logprob": avg_logprob,
            "compression_ratio": compression,
            "no_speech_prob": no_speech,
            "needs_review": bool(reasons) or confidence < REVIEW_CONFIDENCE,
            "hallucination_suspected": hallucination,
            "reasons": reasons,
        }
        scored.append(record)

        if duration > 0:
            total_duration += duration
            weighted_confidence += confidence * duration

    overall = (weighted_confidence / total_duration) if total_duration > 0 else (
        sum(s["confidence"] for s in scored) / len(scored) if scored else 0.0
    )

    flagged = [s for s in scored if s["needs_review"]]
    suspected = [s for s in scored if s["hallucination_suspected"]]

    if not scored:
        risk = "none"
    elif suspected:
        share = len(suspected) / float(len(scored))
        risk = "high" if share >= 0.34 else "medium"
    elif overall < REVIEW_CONFIDENCE:
        risk = "low"
    else:
        risk = "none"

    return {
        "overall_confidence": round(overall, 3),
        "segments": scored,
        "flagged": flagged,
        "hallucination_risk": risk,
        "summary": {
            "segment_count": len(scored),
            "flagged_count": len(flagged),
            "hallucination_suspected_count": len(suspected),
            "audio_seconds": round(total_duration, 2),
        },
    }


def low_confidence_spans(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Character offsets of low-confidence segments within the joined transcript,
    so the UI can highlight exactly the words worth re-listening to.

    Segments are joined with a single space, matching how the transcript is
    assembled for display.
    """
    spans: List[Dict[str, Any]] = []
    cursor = 0
    for seg in analysis.get("segments", []):
        text = seg["text"]
        if not text:
            continue
        start = cursor
        cursor += len(text) + 1  # trailing space
        if seg["needs_review"]:
            spans.append({
                "start": start,
                "end": start + len(text),
                "text": text,
                "confidence": seg["confidence"],
                "reasons": seg["reasons"],
                "hallucination_suspected": seg["hallucination_suspected"],
            })
    return spans
