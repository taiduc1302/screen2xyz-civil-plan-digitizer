# Additional field checks

Date: 2026-08-04  
Branch: `feature/v2.7-agtek-field-fixes`

| Check | Evidence | Result |
|---|---|---|
| Negative second-monitor coordinates | Pure picker drag conversion and `ScreenOcrBackend.read_zone` at `(-582,1009,112,29)`; cursor fixture uses `(-500,1000)` | Passed; negative origins preserved exactly |
| Zone heights 18–30 px | All 13 heights tested; 18–23 px warn about clipping, 24–30 px remain accepted without the tight-height warning | 13/13 passed |
| Grey/low contrast | Real Tesseract, cache disabled, `#a8a8a8` background; foreground intensity 72, 100, 124 (contrast differences 96, 68, 44) | 3/3 correct, 0 wrong accepted, 0 rejected |
| `x` marker | All 12 AGTEK-style cursor reads assert raw output contains neither `x` nor `*` and confidence is at least 0.60 | 12/12 passed |
| Two labels in 160x60 box | Two values each supported by two preprocessing variants; production consensus and spatial selection exercised | Nearest value 49.78 won; 49.47 did not leak |
| Combined AGTEK geometry | One 800x500 fixture with mid-grey drawing, 17 px `x 51.53` at -12°, and light status strip `North: 2,768.313` | Both elevation and northing read exactly; passed |
| Zone with label text | Retained `test_real_viewer_ocr.py` regressions cover `North:` prefixes, grouped numeric tokens, stray punctuation, and numeric-token confidence | 5/5 passed within the full application suite |

The expanded real-field OCR module ran 3 tests in 161.242 seconds. The complete
application suite then passed 75/75 in 171.386 seconds; Civil passed 113/113 and
M2 passed 498/498. All real OCR checks disabled caching.

These fixtures reproduce observed geometry but do not automate or validate a
live third-party viewer window.
