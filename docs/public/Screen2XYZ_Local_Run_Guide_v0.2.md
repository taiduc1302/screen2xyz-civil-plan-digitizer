# Screen2XYZ Local Run Guide v0.2

| Field | Value |
|---|---|
| Scope | Current Windows computer; locally generated synthetic images only |
| Shell | Windows PowerShell 5.1 |
| Python | CPython 3.14.6 |
| Direct third-party project dependencies | None |
| Live capture | Not executed |
| Output classification | Conceptual and preliminary estimating data only. |

This guide reproduces the experimental generated-image OCR laboratory. It does not operate on a real source, capture a live desktop region, transform coordinates, calculate terrain or earthwork, or demonstrate downstream import compatibility.

## 1. Clone or update

New local clone:

```powershell
git clone https://github.com/taiduc1302/screen2xyz.git
Set-Location screen2xyz
git switch feat/overnight-v0.2-planning-ocr-lab
```

Existing clone:

```powershell
git fetch origin --prune
git switch feat/overnight-v0.2-planning-ocr-lab
git pull --ff-only origin feat/overnight-v0.2-planning-ocr-lab
```

## 2. Create the isolated environment

```powershell
py -3.14 -m venv --without-pip .venv
$env:PYTHONPATH = "src"
```

There are no direct third-party project dependencies and no dependency installation command. Do not run `pip install`. Verify the empty distribution inventory:

```powershell
.\.venv\Scripts\python.exe -c "import importlib.metadata; print(sum(1 for _ in importlib.metadata.distributions()))"
```

Expected result: `0`.

## 3. Generate or verify the fixture

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m screen2xyz_lab.cli generate
```

An existing byte-identical fixture returns `VERIFIED_EXISTING`. It is not overwritten.

## 4. Reproduce one OCR evaluation

Use a fresh output path:

```powershell
$env:PYTHONPATH = "src"; $Run = ".lab_work\reproduce-$(Get-Date -Format 'yyyyMMdd-HHmmss')"; .\.venv\Scripts\python.exe -m screen2xyz_lab.cli evaluate --output $Run
```

The command invokes actual local OCR for all 60 generated PNGs. The work output contains raw OCR, accepted/rejected records, classifications, source-coordinate XYZ demonstration output, and a metadata sidecar. It does not publish or overwrite retained evidence.

## 5. Run all tests

The retained full-suite command is:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe tests\run_all.py --output .lab_work\S2XYZ-CODEX-003-test-results.txt
```

The output path must be fresh. The runner does not overwrite retained evidence.

## 6. Locate retained evidence

```powershell
Get-ChildItem -LiteralPath runs\evidence\S2XYZ-CODEX-003 -Recurse
Get-Content -Raw -LiteralPath runs\evidence\S2XYZ-CODEX-003\metrics.json
```

Required retained outputs include `ground_truth.csv`, `raw_ocr_readings.csv`, `accepted_points.csv`, `rejected_readings.csv`, `points_source_xyz.txt`, `points_source_xyz_metadata.json`, `metrics.json`, `environment.json`, `dependency_inventory.txt`, `test_results.txt`, and `evidence_manifest_sha256.txt`.

## 7. Verify retained evidence

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m screen2xyz_lab.cli verify-evidence
```

This is read-only. A valid retained set returns `PASS`.

## 8. Clean only disposable local work

This command resolves and verifies the exact `.lab_work` directory before removal. It never targets `runs/evidence`:

```powershell
$Repo = (Resolve-Path -LiteralPath .).Path
$Target = [System.IO.Path]::GetFullPath((Join-Path $Repo ".lab_work"))
if ([System.IO.Path]::GetDirectoryName($Target) -ne $Repo -or [System.IO.Path]::GetFileName($Target) -ne ".lab_work") { throw "Refusing unexpected cleanup target" }
if (Test-Path -LiteralPath $Target) { Remove-Item -LiteralPath $Target -Recurse -Force }
```

Do not delete or rewrite `runs/evidence/S2XYZ-CODEX-003`.

## Limitations

- Current computer only; broader Windows support was not tested.
- Generated images only; live screen capture is `Not executed`.
- Source coordinates remain geographic degrees in `EPSG:4326` with `SYNTHETIC_LOCAL` elevation reference.
- No transformation, real-source operation, downstream import, terrain calculation, or earthwork calculation was tested.
- No repository licence or public-release authorization exists.

Conceptual and preliminary estimating data only.
