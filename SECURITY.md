# Security Policy

## Reporting a vulnerability

Please do not disclose security vulnerabilities in a public issue. Use GitHub's **Report a vulnerability** form on the repository Security tab to submit a private report to the maintainers.

Include the affected version, reproduction steps, impact, and any suggested mitigation. Avoid attaching real plans, screenshots, captured coordinates, credentials, or personal information; use a minimal synthetic reproduction.

## Supported versions

Security fixes are applied to the current `main` branch. Older prototype code under `legacy/` is retained for reference and is not supported.

## Security boundaries

Screen2XYZ processes local screenshots and plan files. OCR text, file paths, clipboard values, PDFs, images, and spreadsheet text must be treated as untrusted input. Exports formula-escape text values, project data remains local, and capture must not bypass access controls, rate limits, CAPTCHA, or technical protections.
