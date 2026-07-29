# Build Week Submission Draft (private; owner review required before any use)

**Project name:** Screen2XYZ — the trustworthy path from screen to coordinates

**One-liner:** Convert explicitly user-selected on-screen readings into
reviewed, approved, provenance-sealed XYZ data — with AI kept on a leash.

**Problem:** Construction and survey staff retype on-screen coordinates by
hand. Errors are silent and expensive. Naïve "AI reads your screen" tools
make it worse: OCR happily turns a letter O into a zero and hands you a
plausible wrong elevation.

**What we built:** A local-first review lab. You select an image; a
deterministic pipeline OCRs, parses, validates, and classifies it into
candidates; raw OCR is preserved immutably; you correct, reject, or
approve; only approved points export, with a SHA-256 provenance manifest.
Our own evaluation retains the O→0 false accept as the demo's centrepiece —
the product's thesis is that human approval plus evidence sealing is what
makes extraction trustworthy.

**Evidence:** sealed baseline benchmark 42/42 exact / 18/18 rejected /
byte-reproducible; varied M1 set 15/15 exact / 0 false rejects; 76/76
tests; every claim traces to retained hashed artifacts.

**AI usage:** the baseline was built with Codex under an evidence-gated
orchestration workflow; Claude performed independent audits and built M1;
a GPT assistance seam exists but is disabled by default and can never
approve data. Humans hold every approval gate.

**Ask/next:** explicit single-window capture, realistic (still synthetic)
drawing-style evaluation, and a reviewed AI-assist note for ambiguous
candidates.

**Not claimed:** real-drawing accuracy, takeoff/estimating capability,
production readiness. Demo uses synthetic data only.
