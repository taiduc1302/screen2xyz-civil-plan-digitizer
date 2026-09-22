# Security and publication policy

## Public repository; private reports

This repository is publicly visible. Issues, pull requests, comments and Actions
logs may therefore be public. **Do not report credentials, personal information,
proprietary drawings or sensitive findings in a public issue.** Contact the
repository owner through a private channel already available to you. Private
vulnerability reporting has not been verified as enabled here.

There is no supported production deployment or blanket security certification.
The local baseline and optional MCP integrations have different trust boundaries.
A local connector does not by itself mean a connected AI host keeps all data local;
review that host's permissions and data handling before using authorized drawings.

## Retained baseline protections

The baseline documents bounded local OCR subprocesses, fixture identity checks,
CSV formula escaping, atomic copy-on-write evidence, and tracked-content privacy
tests. These controls have a defined baseline scope; they do not prove that every
later branch, integration, binary, Git object or hosted artifact is safe.

Never edit retained evidence to make an audit appear to pass. Review findings,
record their disposition, and preserve legitimate attribution and licence notices.

## Historical audit versus this repository

`AUDIT_AND_REMEDIATION_REPORT.md` is dated 2026-07-17 and explicitly audits the
private parent repository. Its warning about two early author identities is
historical evidence, not a fresh finding against every descendant repository.
`ORIGIN_PROVENANCE.md` records a subsequent standalone export without the parent's
`.git` directory. That provenance statement is also not a current all-ref scan.

The previous policy incorrectly described this public repository as private and
repeated the parent's history finding as if it had been independently verified
here. Neither a confirmed current leak nor a completed cleanup should be inferred
from those inherited statements. Current review scope is in
[PUBLIC_RELEASE_AUDIT.md](PUBLIC_RELEASE_AUDIT.md).

## Required review before promoting a release

Inspect current files and all intended branches/tags, reachable historical
content, author/committer metadata, commit/tag messages, media and archive
metadata, LFS objects, releases, issues/PR text and CI artifacts. Verify rights and
authorizations separately from keyword scans and synthetic test results.

The bounded read-only `tools/publication_audit.py` produces only redacted counts
for locally reachable raw Git objects. It deliberately cannot authorize release.
It does not decode images, PDF streams or archives, and cannot inspect hosted-only
content or other people's clones. See its report limitations and the audit record.

If an actual credential is found, revoke/rotate it before treating deletion as a
remedy. History rewriting requires a verified private backup, coordination with
active contributors and separate owner authorization. Do not force-push, delete
refs, rewrite authorship or change visibility as a side effect of documentation
cleanup. Follow [GitHub's sensitive-data removal guidance](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).
