# Test Matrix

## Automated

```bash
npm run check                     # JS syntax, manifest, Python compile, tests
python3 asr/tests/run_tests.py -v # 45 tests, no external dependencies
```

Automated coverage: abbreviations, medication matching (unigram + bigram),
vitals parsing and range checks, NegEx assertion status, ASR quality and
hallucination detection, sentence splitting, SOAP routing, BM25 ranking, PHI
detection and redaction, and the pipeline's negation → coding edge.

## Manual

| Area | Test | Expected | Owner |
| --- | --- | --- | --- |
| OpenEMR login | Login screen | Panel stays hidden | Tokhirjon |
| OpenEMR encounter | Panel activation | Appears when a fillable field exists | Tokhirjon |
| OpenEMR encounter | Reason-only insert | Transcript lands in Reason for Visit | Tokhirjon |
| OpenEMR encounter | Multi-field insert | SOAP + vitals fill from one analysis | Tokhirjon |
| OpenEMR encounter | Field match strategy | Rows show `name-attribute` on real OpenEMR fields | Tokhirjon |
| OpenEMR encounter | Other field safety | Untick a row; that field is left untouched | Tokhirjon |
| OpenEMR encounter | Overwrite notice | A field with content shows "will overwrite" | Tokhirjon |
| **Style isolation** | **Panel inside OpenEMR** | **Layout intact; host `input{width:100%}` rules must not collapse the panel** | Tokhirjon |
| Confirmation | Cancel the dialog | Nothing is written | Tokhirjon |
| Confirmation | needs_review default | Low-confidence rows start unticked | Tokhirjon |
| Analysis | Stale transcript | Editing after analysis shows the re-analyze notice | Tokhirjon |
| Analysis | Negated finding | "denies chest pain" produces no chest-pain code | Tokhirjon |
| ASR | Hallucination flag | Silence produces a flagged segment | Tokhirjon |
| ASR | Confidence bar | Mumbled speech lowers the bar | Tokhirjon |
| Service | `/capabilities` | Degraded layers are reported, not hidden | Tokhirjon |
| Service | Service down | Panel says offline; demo text still works | Tokhirjon |
| Edge case | Mic denied | Clear message; manual transcript path works | Tokhirjon |
| Edge case | No fields found | Panel stays hidden | Tokhirjon |
| Fixture | encounter-soap-vitals | 11 fields resolve; 10 tick by default | Tokhirjon |
| Fixture | no-reason-field | Panel stays hidden | Tokhirjon |

## Regressions covered by tests

Each of these was a real defect found during development:

| Defect | Test |
| --- | --- |
| NegEx scope crossed sentence boundaries, negating the wrong finding | `negation: scope does not cross a sentence boundary` |
| Decimals split sentences: "38.0" became two fragments | `soap: decimals and abbreviations do not split sentences` |
| Relative-only confidence scored unrelated prose at 1.0 | `coding: unrelated prose yields no confident candidate` |
| Binary phonetic scoring pushed transposition errors below threshold | `medications: transposition errors still resolve` |
| Weak medication matches raised no warning — the wrong half was silenced | `pipeline: a WEAK medication match warns loudest, not least` |
| Cue-word regex was case-sensitive, missing "Patient Maria Gonzalez" | `phi: titles are not captured as names` (same pass) |
| Title captured as a person name ("Dr") | `phi: titles are not captured as names` |
| A split drug name was unrecoverable | `medications: rejoins a drug name the decoder split in two` |

One defect is **not** covered by an automated test and must be checked by hand:
the host page's `input { width: 100% }` collapsing the panel's checkbox column.
It needs a real browser with OpenEMR's stylesheet loaded. See the style
isolation row above.

## Scope

MVP validation, not production QA. OpenEMR's own save-time validation is
separate from DOM insertion.
