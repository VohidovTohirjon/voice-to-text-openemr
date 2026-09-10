# AI/ML Architecture

Technical reference for the machine-learning and language-processing layers in
this project. Written to be presentable: each section states what the layer
does, what technique it uses, why that technique was chosen over the obvious
alternative, and where the code lives.

---

## 1. Design constraints

Three constraints shaped every choice below.

**Everything runs locally.** Patient dictation cannot leave the workstation, so
no hosted API is used anywhere in the pipeline. Privacy is a property of the
architecture, not of a vendor agreement.

**Degrade, never fail.** Each layer either works or reports that it is
unavailable. `GET /capabilities` tells the extension which layers are live so
the UI can hide what it cannot deliver, instead of failing at the moment a
clinician clicks.

**Suggest, never write.** No layer edits the chart. Everything produces ranked
candidates with confidence scores, and a human confirms before anything is
written. A medication name silently "corrected" by a model would be a patient
safety defect.

A practical consequence of the second constraint: the entire clinical pipeline
is pure Python with no ML dependencies. It runs on a machine with neither spaCy
nor a GPU. Whisper is needed only to turn audio into text.

---

## 2. Layer map

```
audio
  |
  +-- [1] Whisper base ................... neural, speech -> text
  |        |
  |        +-- [2] ASR quality ........... statistical, uses Whisper's own decoder stats
  |
transcript
  |
  +-- [3] SOAP structuring .............. rule-based classifier (LLM optional)
  +-- [4] Clinical vocabulary ........... phonetic + edit distance
  +-- [5] Negation (NegEx) .............. rule-based, sentence-scoped
  +-- [6] ICD-10 suggestion ............. Okapi BM25 information retrieval
  +-- [7] PHI detection ................. pattern + NER
  +-- [8] Entity extraction ............. spaCy NER / Llama 3.2 (optional)
  |
field mappings -> clinician confirmation -> OpenEMR form
```

Layers 1 and 8 are neural networks. Layer 2 reads a neural network's internal
state. Layers 3–7 are classical algorithms. Being explicit about which is which
is deliberate: "AI" that turns out to be a regex is worse than a regex that was
described honestly.

---

## 3. Whisper — speech recognition

**File:** `asr/api.py` · **Technique:** transformer encoder–decoder

OpenAI Whisper, `base` variant. Encoder–decoder transformer trained on ~680,000
hours of multilingual audio. `base` was chosen over `small`/`medium` for
latency: transcription must feel immediate during a consultation.

The model is lazy-loaded, so the service starts instantly and the text-only
endpoints stay usable on a machine that has never downloaded the weights.

Override the size with the `WHISPER_MODEL` environment variable.

---

## 4. ASR quality and hallucination detection

**File:** `asr/nlp/asr_quality.py` · **Technique:** decoder statistics

This is the layer most integrations skip. Whisper computes per-segment decoding
statistics and then most callers read only `text` and discard them.

| Signal | Meaning | Threshold |
|---|---|---|
| `avg_logprob` | mean token log-probability; `exp()` gives a confidence | < −1.0 |
| `compression_ratio` | `len(text) / len(zlib(text))`; looping output compresses well | > 2.4 |
| `no_speech_prob` | probability the segment is silence | > 0.6 |

The thresholds are Whisper's own decoding-fallback thresholds, reused as review
thresholds rather than as re-decode triggers.

Two hallucination signatures are detected:

- **Repetition loops** — high compression ratio, or an n-gram repeated three or
  more times.
- **Speech invented over silence** — high `no_speech_prob` combined with
  confident, fluent text. This is a training-data artefact; Whisper will emit
  subtitle boilerplate such as *"Thank you for watching, please subscribe"* over
  a silent passage.

Why this matters clinically: a hallucinated sentence in a chart note is worse
than a missing one, because it reads as fact and carries no marker of doubt.

Output includes character offsets of low-confidence spans so the UI can
highlight exactly which words to re-listen to.

---

## 5. SOAP structuring

**File:** `asr/nlp/soap.py` · **Technique:** cue-phrase scoring classifier

Splits dictation into Subjective / Objective / Assessment / Plan.

Two modes:

- **Header mode** — the clinician dictated "Objective:" or "O:". An explicit
  header is authoritative; confidence is 1.0 and no scoring runs.
- **Scoring mode** — each sentence is scored against weighted cue sets per
  section. The winner is the argmax; confidence comes from the *margin* over the
  runner-up.

The margin matters more than the raw score. "Continue lisinopril" is
unambiguously Plan. "Patient is febrile" reads as both Subjective and Objective,
and a narrow margin is how the UI knows to show that it was a close call.

The sentence splitter is tuned for dictation: it does **not** split on the
decimal point in "temperature 38.0 degrees" or the period in "Dr. Whitfield".
Both produce fragments that then land in the wrong section.

An optional Llama 3.2 3B path via Ollama handles conversational dictation that
cue phrases miss, falling back to the rule classifier on any failure.

---

## 6. Clinical vocabulary

**File:** `asr/nlp/medical.py` · **Technique:** Soundex + edit distance, regex, NegEx

Whisper is a general model. On clinical dictation it fails in three predictable
ways that no decoder improvement fixes, because they need domain knowledge.

### 6a. Medication correction

Drug names are mis-heard constantly. Matching combines three similarity
measures against a 118-entry formulary:

```
score = 0.55 · orthographic  +  0.20 · phonetic  +  0.25 · consonant skeleton
```

- *Orthographic* — `difflib` sequence ratio.
- *Phonetic* — similarity between Soundex codes. **Graded, not binary**: a
  transposition ("metroprolol") changes the Soundex code without making the
  words phonetically unrelated, and an all-or-nothing phonetic term pushes
  common ASR errors below threshold.
- *Consonant skeleton* — vowels stripped. ASR errors cluster in vowels;
  consonants survive.

Two passes run: **unigram** (each word alone) and **bigram** (adjacent words
joined, catching names the decoder split — "lisin opril" → lisinopril). A bigram
is kept only when it beats both constituent words.

Look-alike/sound-alike (LASA) pairs are flagged so the clinician confirms rather
than accepts — hydroxyzine/hydralazine, bupropion/buspirone.

**Known limit, stated plainly:** severe fragmentation is unrecoverable. In a
real Whisper run, "acetaminophen" was transcribed as *"a seed of minifin"*. No
string metric recovers that; the surface form no longer resembles the drug. This
is the concrete, evidence-backed argument for evaluating a medical-domain
acoustic model.

### 6b. Vital signs

Parsed with unit normalisation and physiologic range validation. Temperature
scale is inferred from magnitude when unstated (≈95–108 → Fahrenheit, 35–42 →
Celsius) and both values are returned. Weight converts to kilograms.

Range checks exist to catch transcription damage, not to judge clinical acuity:
a heart rate of 880 or a systolic below diastolic is flagged as a probable
transcription error.

### 6c. Abbreviation expansion

73 curated entries. Two safety behaviours matter more than coverage:

- **Ambiguous terms are marked, not resolved.** "PE" is pulmonary embolism *or*
  physical examination; confidence drops and both readings are shown.
- **ISMP error-prone abbreviations raise a warning.** Terms on the ISMP List of
  Error-Prone Abbreviations (QD, QOD, U, IU, MS, HS, SC/SQ) are flagged with the
  reason they are dangerous, rather than quietly expanded.

Letter-spaced dictation ("b i d") is collapsed before lookup.

### 6d. Negation — NegEx

Implementation of the NegEx algorithm (Chapman et al., 2001), still the baseline
in clinical NLP because it handles roughly 80% of clinical negations.

A trigger term negates findings within a bounded window unless a termination
term closes the scope first:

- **Pre-triggers** — "denies", "no evidence of", "without", "ruled out"
- **Post-triggers** — "was ruled out", "is negative"
- **Terminations** — "but", "however", "except"
- **Pseudo-negations** — "no increase in" does *not* negate
- **Hedges** — "possible", "likely", "cannot rule out" → `uncertain`, not negated

Scope is **sentence-bounded**. Without that bound, "reports headache. Fever was
ruled out." lets the post-trigger reach backwards across the full stop and
negate the headache.

---

## 7. ICD-10 code suggestion

**File:** `asr/nlp/coding.py` · **Technique:** Okapi BM25

Ranks diagnosis codes against assessment text using BM25 — the ranking function
behind Lucene and Elasticsearch — implemented in plain Python.

```
IDF(q)   = ln(1 + (N − df + 0.5) / (df + 0.5))
score(D) = Σ IDF(q) · f(q,D)·(k₁+1) / (f(q,D) + k₁·(1 − b + b·|D|/avgdl))
```

with k₁ = 1.5, b = 0.75, plus a ×1.6 bonus when a multi-word synonym appears
verbatim.

**Why BM25 rather than embeddings.** Diagnosis text is short and the vocabulary
is closed and highly specific ("epigastric", "cerumen", "podagra"). Lexical
ranking with IDF weighting beats a general-purpose sentence embedding on exactly
this shape of problem, needs no model download, returns in microseconds, and —
decisively for a clinical tool — is fully explainable: every suggestion shows
which query terms matched.

**Confidence combines three factors**, because any one alone misleads:

- `strength` — absolute evidence, saturating. Without it, a query with one weak
  accidental match scores 1.0 simply for being top-ranked.
- `share` — this candidate's score relative to the best.
- `separation` — how cleanly the best beats the runner-up. A narrow gap means
  ambiguous, and the UI should show both.

**The negation → coding edge.** "Denies chest pain" contains the phrase "chest
pain". A coder that ignores assertion status will suggest R07.9 for a patient
who explicitly does not have it. Negated findings are stripped before ranking.

**Per-finding coding.** One assessment sentence often carries several conditions
("viral URI with uncontrolled hypertension"). Ranking the sentence as a whole
surfaces only the dominant one, so each affirmed finding is additionally coded
on its own and the results are merged.

---

## 8. PHI detection and de-identification

**File:** `asr/nlp/phi.py` · **Technique:** pattern matching + NER

Covers the HIPAA Safe Harbor identifier list, 45 CFR 164.514(b)(2). Fifteen of
the eighteen identifiers are detectable in free text; the other three
(photographs, biometrics, voiceprints) are properties of the media.

Two detectors merge, with overlaps resolved by confidence:

- **Patterns** — SSN, phone, email, MRN, account and license numbers, URLs, IP
  addresses, dates, ZIP codes.
- **NER** — person names and places via spaCy when installed. Without spaCy a
  title- and context-cued fallback runs, and the response is marked
  `ner_backend: "fallback"` so the caller knows the pass was weaker rather than
  silently trusting it.

Age over 89 is itself an identifier under Safe Harbor and is flagged as such.

Redaction replaces each identifier with a bracketed type placeholder, keeping
the note readable and the redaction auditable.

**Why this belongs in a voice tool specifically.** Dictation captures whatever
is said in the room. A clinician thinking aloud says names, dates of birth, and
phone numbers never meant for the note body. Catching them at the transcript
boundary is cheaper than scrubbing the chart afterwards — and it is what makes
"the audio never leaves the machine" a complete claim rather than half of one.

---

## 9. Field mapping

**File:** `asr/nlp/field_mapper.py`, `extension/scanner.js`

Analysis output is addressed to real OpenEMR fields, taken from the actual form
tables rather than guessed:

| Source table | Fields |
|---|---|
| `form_soap` | `subjective`, `objective`, `assessment`, `plan` |
| `form_vitals` | `bps`, `bpd`, `pulse`, `respiration`, `oxygen_saturation`, `temperature`, `weight` |
| encounter form | `reason` |

The DOM scanner resolves each mapping most-reliable-first: exact `name`
attribute, then `id`, then label text, then `aria-label`, then placeholder. Each
result records *how* it was found, so the confirmation UI can show whether a
field was matched on its real name or merely inferred from a label.

A suggestion the service marked `needs_review` starts **unticked**: the operator
opts in rather than opting out.

---

## 10. Performance

Measured on the bundled test note, warm caches, Python 3.8, Apple Silicon:

| Layer | Time |
|---|---|
| ASR quality | 0.1 ms |
| PHI | 0.2 ms |
| SOAP | 0.2 ms |
| Vitals | 0.1 ms |
| Medications | 29 ms |
| Abbreviations | 0.5 ms |
| Negation | 0.3 ms |
| ICD-10 | 0.2 ms |
| **Total** | **~31 ms** |

Medication matching dominates because it scores every candidate token against
the formulary. Soundex results are memoised, which roughly halved it.

Whisper transcription is separate and depends on audio length and model size;
roughly 3 s for a 25 s clip on `base`.

---

## 11. What is deliberately not here

- **No cloud API**, anywhere in the pipeline.
- **No fine-tuned medical model yet.** Whisper `base` is a general model. The
  "a seed of minifin" failure is the measured argument for evaluating a
  domain-adapted model next.
- **The ICD-10 corpus is a 91-code curated demo subset**, not a licensed
  ICD-10-CM release. It must be replaced with the current CMS/CDC files before
  any billing use.
- **The formulary is 118 hand-curated entries**, not an RxNorm extract.
- **No automatic writing to the chart.** Every layer stops at a suggestion.

---

## 12. Tests

```bash
python3 asr/tests/run_tests.py -v
```

45 tests, no external dependencies — they run without Whisper, spaCy, or a
network. Coverage includes the regressions found while building these layers:
NegEx crossing sentence boundaries, decimals splitting sentences, relative-only
confidence scoring garbage as 1.0, and weak medication matches being the ones
that failed to warn.
