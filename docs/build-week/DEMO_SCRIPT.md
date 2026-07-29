# Demo Script (2–3 minutes, fully local)

Setup (before demo): repository cloned, venv present, `$env:PYTHONPATH = "src"`.

1. **(15 s) The problem.** "Field crews and estimators retype on-screen
   coordinates by hand. One wrong digit poisons the surface. We built the
   trustworthy path from pixels to points."

2. **(30 s) Open the review lab.**
   `.\.venv\Scripts\python.exe -m screen2xyz_m1.cli review`
   "Nothing enters this tool unless I explicitly select it — no background
   capture, no network."

3. **(45 s) Process two images.** Click *Select PNG…* →
   `test_data/synthetic/m1_eval_v0.1/images/M001.png` (clean accept), then
   `M015.png`. "M015 is our trap: the image contains the letter O inside
   the digits. OCR read it as zero — a plausible, wrong coordinate. The raw
   OCR text is preserved right here, immutably, which is how a reviewer
   catches it."

4. **(45 s) Review like a human.** Select M015's candidate → show raw OCR →
   *Reject* it. Select M001's candidate → optionally edit the elevation →
   *Apply correction* ("corrections are stored separately — the original
   parse is never overwritten") → *Approve*.

5. **(30 s) Export.** Click *Export approved*. Open
   `.lab_work/m1_runs/<run_id>/`: approved-only CSV and XYZ, the immutable
   raw records, and `evidence_manifest_sha256.txt`. "Every artifact is
   hashed. Rejected data cannot leak into the export. The status bar says
   'External AI: not used' — assistance is opt-in and can never approve."

6. **(15 s) The credibility exhibit.** Show
   `runs/evidence/S2XYZ-M1-001/m1_eval_metrics.json` and the sealed
   baseline evidence: "42/42 exact readings on the sealed baseline,
   byte-reproducible; 15/15 on the varied M1 set; the one false accept is
   retained on purpose — it is the argument for the product."

Do not claim: real-drawing accuracy, takeoff capability, or production
readiness. If asked, answer: "synthetic controlled evidence today; explicit
window capture and realistic evaluation are the next milestones."
