#!/usr/bin/env python3
"""
Test suite for the clinical NLP layers.

Deliberately dependency-free: plain asserts and a small runner, so it executes
with a bare `python3 asr/tests/run_tests.py` on any machine that can run the
service. Whisper and spaCy are NOT required — every layer under test here is
pure Python, which is the point of the design.

Run:
    python3 asr/tests/run_tests.py
    python3 asr/tests/run_tests.py -v
"""

import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nlp import asr_quality, coding, medical, phi, soap  # noqa: E402
from nlp.pipeline import analyze, capabilities  # noqa: E402

_TESTS = []
_VERBOSE = "-v" in sys.argv


def test(name):
    def decorate(function):
        _TESTS.append((name, function))
        return function
    return decorate


# ---------------------------------------------------------------------------
# medical.py — abbreviations
# ---------------------------------------------------------------------------


@test("abbreviations: expands common clinical shorthand")
def _():
    found = {a["abbreviation"].upper(): a for a in
             medical.expand_abbreviations("Pt with HTN and T2DM, c/o SOB.")}
    assert "HTN" in found, found.keys()
    assert found["HTN"]["expansion"] == "hypertension"
    assert found["SOB"]["expansion"] == "shortness of breath"


@test("abbreviations: flags ISMP error-prone terms and lowers confidence")
def _():
    found = {a["abbreviation"].upper(): a for a in
             medical.expand_abbreviations("Give 10 units QD.")}
    assert "QD" in found
    assert "ismp_error_prone" in found["QD"]
    assert found["QD"]["confidence"] <= 0.6, found["QD"]["confidence"]


@test("abbreviations: marks ambiguous terms rather than guessing")
def _():
    found = {a["abbreviation"].upper(): a for a in
             medical.expand_abbreviations("Concern for PE today.")}
    assert "ambiguous" in found["PE"]
    assert found["PE"]["confidence"] < 0.75


@test("abbreviations: handles letter-spaced dictation (b i d)")
def _():
    found = {a["abbreviation"].upper() for a in
             medical.expand_abbreviations("Take one tablet b i d with food.")}
    assert "BID" in found, found


# ---------------------------------------------------------------------------
# medical.py — medication correction
# ---------------------------------------------------------------------------


@test("prompting: the decoder prompt is built from the bundled formulary")
def _():
    from nlp import prompting
    prompt = prompting.clinical_prompt()
    assert "lisinopril" in prompt and "acetaminophen" in prompt
    assert len(prompt.split()) <= prompting.MAX_PROMPT_WORDS
    options = prompting.decode_options()
    assert options["language"] == "en", "language must be pinned, not detected"
    assert options["temperature"] == 0.0, "decoding must be deterministic"


@test("prompting: caller-supplied terms take precedence in the prompt")
def _():
    from nlp import prompting
    prompt = prompting.clinical_prompt(extra_terms=["insulin glargine", "warfarin"])
    assert prompt.index("insulin glargine") < prompt.index("lisinopril")


@test("medications: corrects a mis-heard drug name confidently")
def _():
    results = {m["heard"]: m for m in
               medical.correct_medications("Patient takes lisinapril daily.")}
    entry = results["lisinapril"]
    assert entry["suggestions"][0]["name"] == "lisinopril"
    assert entry["confident"] is True
    assert entry["needs_review"] is True, "a correction must always be reviewable"


@test("medications: transposition errors still resolve (metroprolol)")
def _():
    results = {m["heard"]: m for m in
               medical.correct_medications("Continue metroprolol 25 mg.")}
    assert results["metroprolol"]["suggestions"][0]["name"] == "metoprolol"


@test("medications: exact formulary hits are not flagged for review")
def _():
    results = {m["heard"]: m for m in
               medical.correct_medications("Start atorvastatin at bedtime.")}
    entry = results["atorvastatin"]
    assert entry["exact"] is True
    assert entry["needs_review"] is False


@test("medications: ordinary prose produces no suggestions")
def _():
    prose = "Patient presents today complaining of persistent morning stiffness."
    assert medical.correct_medications(prose) == []


@test("medications: rejoins a drug name the decoder split across words")
def _():
    # Every one of these is a transcript this project's Whisper actually
    # produced, including the two-letter fragments an earlier version could not
    # reach because it only scanned tokens of four or more characters.
    measured = (
        ("Continue lisin opril 10 mg daily.", "lisinopril"),
        ("Start atorva statin at bedtime.", "atorvastatin"),
        ("Give amoxi cillin for ten days.", "amoxicillin"),
        ("Continue metform in 1000 mg twice daily.", "metformin"),
        ("Continue at torvastatin 40 mg at bedtime.", "atorvastatin"),
        ("Continue leave othiroxin 75 micrograms daily.", "levothyroxine"),
    )
    for text, expected in measured:
        results = medical.correct_medications(text)
        assert results, text
        top = results[0]
        assert top["suggestions"][0]["name"] == expected, (text, top)
        assert top["source"].startswith("window-"), (text, top["source"])


@test("medications: joined windows do not fire on ordinary word pairs")
def _():
    # "walk in clinic" matched "insulin" once the window widened to include
    # two-letter fragments, which is why a joined hypothesis has to clear a
    # higher score than a single word.
    for prose in ("She was seen last week in the walk in clinic and felt better.",
                  "Follow up scheduled with the primary care provider next month.",
                  "Blood pressure well controlled since the last office visit.",
                  "No known drug allergies. Patient lives alone and works as a teacher.",
                  "On examination temperature 38 degrees, blood pressure 148 over 92."):
        assert medical.correct_medications(prose) == [], prose


@test("medications: look-alike/sound-alike pairs are surfaced")
def _():
    results = {m["heard"]: m for m in
               medical.correct_medications("Continue hydroxyzine nightly.")}
    assert "hydralazine" in results["hydroxyzine"]["suggestions"][0]["lasa"]


# ---------------------------------------------------------------------------
# medical.py — vitals
# ---------------------------------------------------------------------------


@test("vitals: parses a full set and normalises units")
def _():
    text = ("Blood pressure 148 over 92, heart rate 88, respiratory rate 16, "
            "temperature 100.4 degrees, O2 sat 96%, weight 185 pounds.")
    by_type = {v["type"]: v for v in medical.extract_vitals(text)}
    assert by_type["blood_pressure"]["systolic"] == 148
    assert by_type["blood_pressure"]["diastolic"] == 92
    assert by_type["heart_rate"]["value"] == 88
    assert by_type["temperature"]["value"] == 38.0, by_type["temperature"]
    assert by_type["temperature"]["unit"] == "C"
    assert by_type["weight"]["value"] == 83.9, by_type["weight"]
    assert by_type["weight"]["unit"] == "kg"


@test("vitals: infers the temperature scale from magnitude")
def _():
    fahrenheit = medical.extract_vitals("temperature 98.6")[0]
    celsius = medical.extract_vitals("temperature 37.0")[0]
    assert fahrenheit["value"] == 37.0, fahrenheit
    assert celsius["value"] == 37.0, celsius
    assert fahrenheit["scale_inferred"] is True


@test("vitals: implausible values are flagged, not silently accepted")
def _():
    flagged = medical.extract_vitals("heart rate 880 today")
    assert flagged[0]["plausible"] is False
    assert "warning" in flagged[0]


@test("vitals: systolic below diastolic is caught")
def _():
    result = medical.extract_vitals("Blood pressure 80 over 120")[0]
    assert result["plausible"] is False


# ---------------------------------------------------------------------------
# medical.py — negation
# ---------------------------------------------------------------------------


@test("negation: pre-trigger negates findings in scope")
def _():
    result = {n["finding"]: n for n in medical.detect_negation(
        "Patient denies chest pain and shortness of breath.",
        ["chest pain", "shortness of breath"])}
    assert result["chest pain"]["status"] == "negated"
    assert result["shortness of breath"]["status"] == "negated"


@test("negation: a termination term closes the scope")
def _():
    result = {n["finding"]: n for n in medical.detect_negation(
        "Denies chest pain but reports headache.", ["chest pain", "headache"])}
    assert result["chest pain"]["status"] == "negated"
    assert result["headache"]["status"] == "affirmed", result["headache"]


@test("negation: scope does not cross a sentence boundary")
def _():
    result = {n["finding"]: n for n in medical.detect_negation(
        "Reports headache. Fever was ruled out.", ["headache", "fever"])}
    assert result["headache"]["status"] == "affirmed", result["headache"]
    assert result["fever"]["status"] == "negated"


@test("negation: hedging is uncertain, not negated")
def _():
    result = medical.detect_negation("Possible migraine.", ["migraine"])[0]
    assert result["status"] == "uncertain", result


@test("negation: pseudo-negations do not negate")
def _():
    result = medical.detect_negation(
        "No increase in chest pain since last visit.", ["chest pain"])[0]
    assert result["status"] == "affirmed", result


# ---------------------------------------------------------------------------
# asr_quality.py
# ---------------------------------------------------------------------------


@test("asr quality: log-probability maps to a bounded confidence")
def _():
    assert 0.0 <= asr_quality.segment_confidence(-0.1) <= 1.0
    assert asr_quality.segment_confidence(-0.1) > asr_quality.segment_confidence(-2.0)
    assert asr_quality.segment_confidence(None) == 0.0


@test("asr quality: repetition loops are flagged as hallucination")
def _():
    result = asr_quality.analyze_segments([{
        "start": 0, "end": 5,
        "text": "follow up follow up follow up follow up follow up",
        "avg_logprob": -0.5, "compression_ratio": 3.1, "no_speech_prob": 0.1,
    }])
    assert result["segments"][0]["hallucination_suspected"] is True
    assert result["hallucination_risk"] == "high"


@test("asr quality: a short repetition loop is caught")
def _():
    # Regression, from a real run on the OpenEMR encounter form: Whisper looped
    # "follow up" five times - ten words. The detector only scanned 4-grams and
    # required size*times (12) words, so it needed twelve words to fire and
    # missed this entirely. Confidence dropped, but nothing said "hallucination".
    text = "Follow up follow up follow up follow up follow up."
    assert asr_quality._repeated_ngram(text) == "follow up", text
    result = asr_quality.analyze_segments([{
        "start": 0, "end": 6, "text": " " + text,
        "avg_logprob": -0.62, "compression_ratio": 1.9, "no_speech_prob": 0.08,
    }])
    assert result["segments"][0]["hallucination_suspected"] is True
    assert result["hallucination_risk"] == "high"


@test("asr quality: repeated phrases in normal prose are not a loop")
def _():
    # A repeat count alone is not enough: this says "follow up" three times and
    # is perfectly ordinary dictation. Coverage of the segment is what separates
    # a decoder loop from emphasis.
    for prose in (
        "Follow up in one week. We will follow up on the labs and follow up on "
        "the referral as well as review the imaging results at that visit.",
        "Plan is acetaminophen 500 milligrams, continue lisinopril daily, "
        "follow up in one week.",
        "Patient reports headache and mild fever for two days. She denies chest pain.",
    ):
        assert asr_quality._repeated_ngram(prose) is None, prose


@test("asr quality: fluent text over silence is flagged")
def _():
    result = asr_quality.analyze_segments([{
        "start": 0, "end": 4,
        "text": "Thank you for watching this video and please subscribe.",
        "avg_logprob": -0.22, "compression_ratio": 1.6, "no_speech_prob": 0.88,
    }])
    assert result["segments"][0]["hallucination_suspected"] is True


@test("asr quality: clean speech is not flagged")
def _():
    result = asr_quality.analyze_segments([{
        "start": 0, "end": 4,
        "text": "Patient reports headache and mild fever for two days.",
        "avg_logprob": -0.18, "compression_ratio": 1.42, "no_speech_prob": 0.02,
    }])
    assert result["segments"][0]["needs_review"] is False
    assert result["hallucination_risk"] == "none"


@test("asr quality: empty input degrades cleanly")
def _():
    result = asr_quality.analyze_segments([])
    assert result["hallucination_risk"] == "none"
    assert result["overall_confidence"] == 0.0


# ---------------------------------------------------------------------------
# soap.py
# ---------------------------------------------------------------------------


@test("soap: decimals and abbreviations do not split sentences")
def _():
    assert len(soap.split_sentences("Temperature 38.0 degrees and BP 118 over 76.")) == 1
    assert len(soap.split_sentences("Referred by Dr. Whitfield today. Plan follows.")) == 2
    assert len(soap.split_sentences("O2 sat 97.5% on room air. Weight 82.3 kg.")) == 2


@test("soap: free dictation routes to the right sections")
def _():
    text = ("Patient reports headache for two days. "
            "On examination temperature 38.0 degrees, alert and oriented. "
            "Impression is likely viral illness. "
            "Plan is rest and fluids, follow up in one week.")
    sections = soap.render_sections(soap.structure_note(text))
    assert "reports headache" in sections["subjective"]
    assert "examination" in sections["objective"]
    assert "Impression" in sections["assessment"]
    assert "follow up" in sections["plan"]


@test("soap: explicit headers override scoring and are fully confident")
def _():
    text = ("Subjective: cough for three days. Objective: temperature 37.8. "
            "Assessment: acute bronchitis. Plan: azithromycin 250 mg.")
    structured = soap.structure_note(text)
    assert structured["mode"] == "header"
    assert structured["confidence"] == 1.0
    sections = soap.render_sections(structured)
    assert "bronchitis" in sections["assessment"]
    assert "azithromycin" in sections["plan"]


@test("soap: empty input degrades cleanly")
def _():
    assert soap.structure_note("")["mode"] == "empty"


# ---------------------------------------------------------------------------
# coding.py
# ---------------------------------------------------------------------------


@test("coding: ranks the correct code first for common presentations")
def _():
    expected = [
        ("urinary tract infection with dysuria", "N39.0"),
        ("acute low back pain after lifting", "M54.50"),
        ("annual physical, routine checkup", "Z00.00"),
        ("sore throat and fever, likely viral pharyngitis", "J02.9"),
    ]
    for query, code in expected:
        top = coding.suggest_codes(query, top_n=1)
        assert top, "no candidate for " + query
        assert top[0]["code"] == code, (query, top[0]["code"], code)


@test("coding: unrelated prose yields no confident candidate")
def _():
    for query in ("the weather is nice today and I like pizza",
                  "let me tell you about my vacation plans"):
        results = coding.suggest_codes(query)
        assert not results or results[0]["confidence"] < 0.75, (query, results[:1])


@test("coding: suggestions carry explainable matched terms")
def _():
    top = coding.suggest_codes("urinary tract infection", top_n=1)[0]
    assert top["matched_terms"], top
    assert top["phrase_match"] == "urinary tract infection"


# ---------------------------------------------------------------------------
# phi.py
# ---------------------------------------------------------------------------


@test("phi: finds structured identifiers")
def _():
    text = ("DOB: 03/14/1958, MRN: A4471928, phone 217-555-0143, "
            "email maria.g@example.com")
    types = phi.detect_phi(text)["by_type"]
    for expected in ("mrn", "phone", "email"):
        assert expected in types, (expected, types)


@test("phi: age over 89 is treated as an identifier")
def _():
    types = phi.detect_phi("She is 94 years old.")["by_type"]
    assert "age_over_89" in types
    assert "age_over_89" not in phi.detect_phi("She is 62 years old.")["by_type"]


@test("phi: titles are not captured as names")
def _():
    names = [e["text"] for e in phi.detect_phi("Referred by Dr. Alan Whitfield.")["entities"]
             if e["type"] == "name"]
    assert "Dr" not in names, names
    assert "Alan Whitfield" in names, names


@test("phi: redaction replaces every detected identifier")
def _():
    text = "Patient Maria Gonzalez, phone 217-555-0143."
    result = phi.redact(text)
    assert "217-555-0143" not in result["redacted_text"]
    assert "[PHONE]" in result["redacted_text"]
    assert result["replacement_count"] >= 2


@test("phi: clean clinical prose triggers nothing")
def _():
    result = phi.detect_phi("Assessment: acute bronchitis. Plan: azithromycin 250 mg.")
    assert result["risk"] == "none"
    assert result["entities"] == []


# ---------------------------------------------------------------------------
# pipeline.py
# ---------------------------------------------------------------------------


_NOTE = (
    "Patient reports headache and mild fever for two days. She denies chest pain. "
    "On examination temperature 38.0 degrees, blood pressure 148 over 92, pulse 96. "
    "Impression is likely viral upper respiratory infection with uncontrolled hypertension. "
    "Plan is acetaminophen 500 mg, continue lisinapril 10 mg daily, follow up in one week."
)


@test("pipeline: negated findings are excluded from code suggestions")
def _():
    result = analyze(_NOTE)
    assert "chest pain" in result["findings"]["negated"]
    assert "chest pain" in result["icd10"]["excluded_negated_findings"]
    codes = {c["code"] for c in result["icd10"]["candidates"]}
    assert "R07.9" not in codes, "chest pain was negated but still coded"


@test("pipeline: each affirmed finding gets its own code candidate")
def _():
    per_finding = {c["finding"]: c["code"] for c in analyze(_NOTE)["icd10"]["per_finding"]}
    assert per_finding.get("hypertension") == "I10", per_finding
    assert per_finding.get("headache") == "R51.9", per_finding


@test("pipeline: vitals reach the real OpenEMR field names")
def _():
    mappings = {m["entity_type"]: m for m in analyze(_NOTE)["field_mappings"]}
    assert mappings["blood_pressure_systolic"]["openemr_fields"][0] == "bps"
    assert mappings["blood_pressure_diastolic"]["openemr_fields"][0] == "bpd"
    assert mappings["heart_rate"]["openemr_fields"][0] == "pulse"
    assert mappings["assessment"]["openemr_fields"] == ["assessment"]


@test("pipeline: mis-heard medication raises a warning")
def _():
    messages = " ".join(w["message"] for w in analyze(_NOTE)["warnings"])
    assert "lisinopril" in messages, messages


@test("pipeline: a WEAK medication match warns loudest, not least")
def _():
    # Regression: warnings previously fired only for confident matches, which
    # silenced exactly the cases needing review. From a real Whisper run.
    warnings = analyze("Continue lycinopryl daily.")["warnings"]
    medication_warnings = [w for w in warnings if "lisinopril" in w["message"]]
    assert medication_warnings, warnings
    assert medication_warnings[0]["level"] == "high", medication_warnings


@test("pipeline: empty transcript returns a clean empty result")
def _():
    result = analyze("   ")
    assert result["empty"] is True
    assert result["field_mappings"] == []


@test("pipeline: completes well inside an interactive budget")
def _():
    analyze(_NOTE)                     # warm the caches
    result = analyze(_NOTE)
    assert result["timings_ms"]["total"] < 400, result["timings_ms"]


@test("pipeline: capabilities reports honestly when spaCy is absent")
def _():
    layers = capabilities()["layers"]
    assert layers["icd10_coding"]["available"] is True
    try:
        import spacy  # noqa: F401
        expected = True
    except ImportError:
        expected = False
    assert layers["entity_extraction"]["available"] is expected


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def main() -> int:
    passed, failed = 0, []
    for name, function in _TESTS:
        try:
            function()
            passed += 1
            if _VERBOSE:
                print("  PASS  " + name)
        except Exception:
            failed.append((name, traceback.format_exc()))
            print("  FAIL  " + name)

    print("\n{0} passed, {1} failed, {2} total".format(passed, len(failed), len(_TESTS)))
    for name, trace in failed:
        print("\n--- " + name + " ---")
        print(trace)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
