# Repository Working Rules

## READ THIS FIRST
Before any work in this repository, read `docs/PROJECT_LOG.md` in full.
It records where the work lives (NOT on `main`), every decision taken, every measurement
made, and the traps that have already cost sessions of wasted effort.
After any significant change, append to its Decision log and Measurement log in the same
commit. A change that alters behavior or produces a number, without a log entry, is
incomplete.

- Preserve previous evidence and never delete or overwrite retained run evidence.
- Use copy-on-write development and task-specific branches.
- Keep changes limited to the approved task and follow current requirements and architecture.
- Do not invent test results, validation outcomes, evidence, or completed capabilities.
- Keep the application source-agnostic; do not add service-specific scraping presets.
- Do not bypass CAPTCHA, rate limits, access controls, or technical protections.
- Use only synthetic, locally generated, government open, or appropriately licensed public demonstration data.
- Do not add proprietary, copied, or unlicensed datasets or interface assets.
- Treat all results as conceptual and preliminary unless authoritative validation exists.
- Keep run transcripts, reports, and evidence traceable to their task and branch.
- Keep UI logic thin and put testable behavior in headless modules.
- Run the relevant application and Civil regression suites before claiming a change works.
