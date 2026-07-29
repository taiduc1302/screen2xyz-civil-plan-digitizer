# Screen2XYZ Synthetic Fixture Specification v0.1

| Field | Value |
|---|---|
| Fixture ID | DS-SYN-001 |
| Fixture version | v0.1 |
| Status | Frozen for the G4-authorized scoped laboratory evaluation |
| Seed | `20260715` |
| Scenario count | Exactly 60 |
| Data origin | Locally generated synthetic project data only |
| Output classification | Conceptual and preliminary estimating data only. |

## 1. Purpose and boundary

Provide deterministic visible English coordinate/elevation text, generated PNG inputs, evaluator-only expected values, and runtime-only image manifests for actual local OCR evaluation. Values are synthetic and are not copied from a real location, source, service, screenshot, interface, or dataset.

## 2. Rendering profiles

All images are 1600 by 260 pixels, PNG, white background, black Arial regular, 96 DPI, anti-aliased grid-fit text, with the origin at x=30/y=80. The OS font is used in place and is not committed.

| Condition ID | Scale label | Font size | Scenarios |
|---|---:|---:|---:|
| `baseline` | 100% | 32 px | 20 |
| `scale_125` | 125% | 40 px | 20 |
| `scale_150` | 150% | 48 px | 20 |

The fixed profile values are configuration, not an assertion about Windows display scaling or universal OCR performance.

## 3. Exact per-condition sequence template

For each condition, local positions 1-20 are mutually exclusive:

| Position | Class | Expected disposition | Rule |
|---:|---|---|---|
| 1 | ordinary valid A | ACCEPT | Provides stale/duplicate reference A |
| 2 | stale A | REJECT_STALE | Exact triplet from position 1; sequence-adjacent |
| 3 | ordinary valid B | ACCEPT | Provides stale/duplicate reference B |
| 4 | stale B | REJECT_STALE | Exact triplet from position 3; sequence-adjacent |
| 5-14 | ordinary valid | ACCEPT | Ten unique triplets |
| 15-16 | valid negative elevation | ACCEPT | Unique triplets with elevation below zero |
| 17 | malformed latitude | REJECT_MALFORMED | Label present; non-decimal latitude token |
| 18 | missing elevation | REJECT_MISSING | `elev` label/value absent |
| 19 | duplicate A | REJECT_DUPLICATE | Matches position 1; non-adjacent |
| 20 | duplicate B | REJECT_DUPLICATE | Matches position 3; non-adjacent |

Per condition this yields 12 ordinary valid, 2 additional valid negative elevation, 2 malformed/missing, 2 stale, and 2 duplicate. Overall: 42 expected-valid and 18 expected-invalid.

Global scenario IDs are `S001` through `S060` in condition order `baseline`, `scale_125`, `scale_150`. Global sequence equals the numeric ID. Reference IDs remain inside the same condition.

## 4. Synthetic value generation

Use Python `random.Random(20260715)` only in the evaluator-side fixture generator. Generate unique canonical base triplets with:

- latitude uniformly from `[-75.000000, 75.000000]`, quantized by constructing exactly six fractional digits;
- longitude with both signs, from `[-170.000000, 170.000000]`, exactly six fractional digits;
- ordinary elevation from `[0.00, 2500.00]`, exactly two fractional digits;
- negative-elevation cases from `[-250.00, -0.01]`, exactly two fractional digits;
- no triplet equal to another unique base triplet;
- no boundary chosen from a known real location or external list.

The generator uses integer microdegrees/cents and Decimal serialization, not binary floating-point rounding. Duplicate and stale visible values are copied only inside evaluator/render-job generation from the declared synthetic references; runtime classification never sees those expected relationships.

## 5. Visible text variants

Every rendered case visibly uses case-insensitive exact English labels `LAT`, `LON`, and `ELEV`. Controlled variants rotate deterministically:

1. `LAT: <v>   LON: <v>   ELEV: <v> m`
2. `LAT = <v>    LON = <v>    ELEV = <v> m`
3. `LAT <v> deg     |     LON <v> deg     |     ELEV <v> m`
4. Three lines: `LAT:`, `LON:`, `ELEV:` with one field per line.

The parser accepts case, permitted separators/whitespace/degree symbol or exact `deg` designator/optional `m`, not OCR label aliases. Malformed latitude uses a letter inside the numeric token. Missing elevation omits both its label and value. Positive and negative longitude and elevation are asserted by coverage tests.

## 6. Artifact separation

Evaluator/render side under `test_data/synthetic/s2xyz_fixture_v0.1/`:

- `fixture_config.json`: canonical profiles, schema, seed, CRS/unit/reference, limits;
- `render_jobs.json`: scenario ID, exact visible text, condition, target image path;
- `ground_truth.csv`: expected values/disposition/code/reference;
- `images/S001.png` through `images/S060.png`.

Runtime-only manifest:

- `fixture_manifest.json`: scenario ID, sequence, condition, relative image path, image hash, dimensions, bytes, config hash. It MUST NOT contain visible text, expected values, class, disposition, code, or reference.

Only the renderer reads `render_jobs.json`. OCR and all runtime domain components read `fixture_manifest.json` and images. Only the evaluator reads `ground_truth.csv` after classifications exist.

## 7. Deterministic serialization and hashes

- Canonical JSON: UTF-8 no BOM, sorted keys, compact separators, final LF.
- Ground-truth CSV: exact Data Dictionary CSV dialect and stable header/order.
- PNG profile and encoder are fixed through the current Windows renderer.
- All image and file hashes use lowercase SHA-256.
- No creation timestamp, absolute path, hostname, username, or random run ID enters deterministic fixture artifacts.

## 8. Fixture validation

Tests must prove exact counts, unique IDs/sequences, three profiles, two signs for longitude, positive/negative elevation, malformed latitude, missing elevation, correct adjacent stale references, correct non-adjacent duplicate references, unique accepted base triplets, path/hash/dimension/byte constraints, synthetic register entry, and expected/runtime separation.

Generated PNG metadata must be empty or limited to an approved non-identifying allowlist before commit.

## 9. Limitations

This fixture covers only three controlled generated text profiles, English labels, one OS font, current Windows rendering/OCR, decimal degrees, metres, and `SYNTHETIC_LOCAL`. It is not a real-source, display-compatibility, location-accuracy, survey, live-capture, transformation, or downstream-import fixture.
