# Retained failed final verification attempt

Date: 2026-08-04  
Commit: `2fc4375d840088899f7537ca54ce57dd18a95b52`

The first final-round harness was cache-disabled and used a fresh output
directory. It failed after 1277.325 seconds:

- exact rows: 173/220 (78.636%);
- captured rows: 217;
- wrong accepted / hallucinated rows: 44;
- safe OCR/parse failures: 3;
- false duplicates: 0;
- SQLite/XLSX exact parity: true.

The failure repeated ten plan-label errors across status styles, including
`53.32 → 93.32` and `55.54 → 95.54`. The general-image OCR path returned the
first weak two-variant consensus, while cursor selection measured all competing
support. Direct support analysis showed wrong alternatives at 1–6 distinct
variants and correct alternatives at 9–19.

The failed generated output remains under
`.lab_work/final-round-1/harness/`; its exact metrics and failure list were not
overwritten. Final verification must restart after the correction.
