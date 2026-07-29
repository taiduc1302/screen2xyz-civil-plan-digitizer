# Standalone Local Development Policy

This repository is the local development destination for the Screen2XYZ Civil
Plan Digitizer. It is intentionally separate from the private hackathon
repository from which the initial tracked tree was exported.

## Remote and publication boundary

- No Git remote may be configured until the owner explicitly supplies and
  approves a new repository URL for this standalone product.
- Never add the hackathon repository as a remote.
- Never push, open a pull request, create a tag/release, or publish from this
  repository without a separate owner decision.
- The tracked `.githooks/pre-push` hook rejects every push. Local Git config
  must keep `core.hooksPath=.githooks` until the owner separately reviews its
  removal.

## Confidential validation boundary

- Real drawings are local validation inputs, not product source.
- Keep confidential PDFs, plan crops, screenshots, projects, exports, and
  machine-readable evaluation results only in ignored local folders.
- Never upload drawing content to OCR, AI, analytics, or other network
  services. PDF extraction, rendering, and OCR are local-only.
- Never commit `Civil IFCclean for gradeworks.pdf` or any derivative page/crop.
- Evidence committed to Git must contain only sanitized aggregate results and
  synthetic fixtures.

## Development boundary

- Make all new functional changes in this standalone repository only.
- Keep local commits; do not rewrite the origin backup or the standalone root
  provenance commit.
- Preserve copyright notices, third-party notices, dependency attribution, and
  original authorship provenance.
- Do not claim AGTEK, Kubla, survey, engineering, or real-page accuracy without
  the corresponding recorded validation.
