# Defect 1 — declared formats and AGTEK-style status OCR

Date: 2026-08-04 (America/Vancouver)

## Reproduction before the fix

Real shipped parser output at v2.6:

```text
'2,768.313' point -> OK 2768.313
'1,718.819' point -> OK 1718.819
'1.844.850' point -> MALFORMED_NUMBER None
'1.844.850' auto -> OK 1844850
```

This reproduces the safety trap exactly: switching to `auto` would silently accept a value about 1000 times too large.

A local synthetic AGTEK-style strip rendered 12 North/East pairs using 12 px Liberation Sans, dark-grey text on a light 29 px strip, with 112x29 and 104x29 crops. Real Tesseract, the shipped fixed-zone policy, and cache disabled produced:

```text
correct=24/24 wrong-accepted=0 rejected=0
```

The synthetic strip did **not** reproduce the operator's real-window failure. This record therefore makes no before/after OCR-rate improvement claim.

## Red state

`tests_app.test_declared_formats` failed to import because no declared-format contract existed. Its seven tests cover all formats, plain/grouped separation, the repeated-separator slip, unique/zero/multiple range interpretations, no `auto` fallback, profile persistence, and actionable OCR errors.

## Green state

```text
Declared-format regressions: 7/7 PASS
Punctuation-slip recovery with unique range: 4/4
AGTEK-style status strip: 24/24 correct, 0 wrong-accepted, 0 rejected
App suite: 63/63
Civil suite: 113/113
M2 suite: 498/498
```

For each declared format, the malformed token recovered to `1844.850` only with range `(1800,1900)`. With no range it remained malformed; with a broad range admitting multiple interpretations it was rejected as `AMBIGUOUS_NUMBER_FORMAT`; with no fitting interpretation it was rejected as `OUT_OF_RANGE`.

## Scope

This evidence uses locally generated pixels, not a live AGTEK window. Operator validation on the real viewer remains required.
