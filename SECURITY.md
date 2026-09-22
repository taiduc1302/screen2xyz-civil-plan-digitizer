# Security and public-data policy

This is publicly visible research source, not a supported production deployment.
Never put sensitive reports, drawings, credentials or private screenshots in
public issues or pull requests. Use GitHub private vulnerability reporting only
when it is enabled; otherwise contact the maintainer through a private channel.

## Public inputs

Only deliberately synthetic fixtures belong in the repository. Real drawings,
project ledgers, company procedures, exported quantities, user home paths,
access tokens and local AI transcripts must stay outside Git and releases.
The source-snapshot checker is `python tools/publication_check.py`.
An allowlisted image hash proves file identity, not drawing accuracy.

## Application boundary

Treat external PDFs, OCR, model output and MCP results as untrusted. Keep the
source PDF immutable and use a separately registered working copy for markups.
The estimator must verify feature identity and scale independently; QA/reference
geometry is never a bid quantity. AI does not grant estimator approval.

Local parsing does not mean an AI host is offline: the selected host/provider
may receive content returned through MCP. Check its data permissions before use.
Do not expose local MCP/GUI services to an untrusted network.

## September 2026 privacy remediation

Real operator inputs were excluded from the rewritten ordinary branch/tag
histories. Original evidence remains in an encrypted, restore-verified backup.
Do not push an old local clone or an old branch back into the public repository.
Re-clone after the rewrite, then port only individually reviewed source changes.
Rewriting a branch does not purge GitHub cached objects, server-managed PR refs,
previous downloads or third-party clones; those require separate handling.
See `PUBLIC_RELEASE_AUDIT.md` for the actual checks and residual scope.
