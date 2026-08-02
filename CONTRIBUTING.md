# Contributing

Thank you for helping improve Screen2XYZ. Read `AGENTS.md`, keep changes source-agnostic, and open focused pull requests from task-specific branches.

## Development setup

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
$env:PYTHONPATH = "src"
```

Run the headless application and Civil regression suites before submitting:

```powershell
.\.venv\Scripts\python -m unittest discover -s tests_app -t . -v
.\.venv\Scripts\python tests_civil\run_civil_tests.py
```

Windows-specific capture behavior should also be exercised on Windows. Do not commit real project drawings, screenshots, credentials, customer information, or generated `.screen2xyz` project databases.

New behavior needs reproducible tests. Never invent OCR accuracy, validation, performance, or compatibility results. Treat outputs as conceptual and preliminary unless authoritative validation exists.
