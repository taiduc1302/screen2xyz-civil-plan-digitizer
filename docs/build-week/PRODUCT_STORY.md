# Product Story

**Screen2XYZ: from what you can see to data you can trust.**

Estimators and field engineers constantly see coordinate and elevation
readings on screen — viewers, monitoring dashboards, survey tools — and
today they retype them into spreadsheets by hand. Retyping is slow and,
worse, silently wrong: one transposed digit becomes a bad surface, a bad
quantity, a bad bid.

Screen2XYZ converts an explicitly user-selected image into structured XYZ
candidates — and then refuses to trust itself. Every value arrives with its
raw OCR text preserved, every transformation is deterministic and hashed,
invalid readings are rejected with machine-readable reasons, and **nothing
is exported until a human explicitly approves it**. Our controlled
evaluation even retains a case where OCR read a letter `O` as a zero and
produced a plausible wrong coordinate — the exact failure mode that makes
"AI read my drawing" products dangerous, and the reason our review step is
mandatory, not optional.

The differentiator is not OCR. It is the evidence discipline: byte-
reproducible runs, sealed hash manifests, honest rejection taxonomy, and a
human approval gate. That is what construction data workflows actually need
before anyone should trust automation with quantities.

Current status: working local prototype over synthetic and user-selected
PNGs. Not a takeoff tool, not CAD, not validated on real drawings — yet.
