# Publication review - 2026-09-22

**READY_FOR_PUBLIC_RELEASE: NO**

This is a bounded publication review, not a completed forensic/security audit,
licence clearance, estimator sign-off, or native Bluebeam acceptance record.

## Source snapshots inspected

- Repository metadata and branch/PR inventory via the connected GitHub API.
- Default branch: `feature/assisted-c03-validation` at
  `51dae379a269639fc04886329bcda3040894ff84`.
- Integration baseline: `main` at
  `077f2b110498269bbd41c592fd0e68865ccfc21d`.
- Related experimental branch: `task/plan-layer-extraction` at
  `a99b2b24e536a4a3a3a3a5dd2fcc7e4aa469bc030b`.
- README, SECURITY, parent audit, origin provenance, control-state files,
  repository sanitization test, relevant draft PR descriptions and source tree.

## Corrections made by this change

1. Replace inaccurate current-private/not-yet-integrated front-page wording with
   a dated branch map and explicit experimental status.
2. Correct security-reporting guidance: issues and PRs in this public repository
   must not receive sensitive reports.
3. Distinguish the 2026-07-17 parent-repository history finding from the subsequent
   standalone export. Do not call that inherited warning a confirmed current leak
   or claim it was remediated by this documentation change.
4. Add an issue-4 reader entrypoint with exact source-snapshot links. Do not invent
   a new Bluebeam implementation, demonstration, approval or measurement result.
5. Add a bounded, read-only, redacted reachable-history pattern scan and separate
   synthetic regression tests. No Git history, evidence, licence or access setting
   is rewritten by these additions.

## Validation actually performed

Seven new audit-tool regression tests passed locally on synthetic Git fixtures:
clean scan without release authorization, deleted history, a non-current branch,
commit metadata, redacted output, bounded-object incompleteness, and shallow-clone
rejection. This validates those scanner behaviours only.

A full clone from this authoring runtime failed because the GitHub hostname could
not be resolved. Repository reading and writes use the connected API. Consequently
no local all-object scan, full application suite, Windows/Revu test, or fresh
application install is claimed by this review.

The added GitHub Actions workflow can run the new tests and a full-depth checkout
scan on a hosted runner. Consult the exact commit's Actions result; merely adding
that workflow does not mean it ran or passed. Findings, skipped content and missing
coverage must be reviewed even if other CI checks pass.

## Checks still required

- Run and review the reachable-history scan, including every intended public
  branch/tag and author/committer metadata. Classify matches rather than deleting
  legitimate attribution or synthetic negative-test fixtures blindly.
- Independently inspect images, archives, decoded PDF streams, LFS content,
  release assets, hosted issues/PR text, Actions artifacts and other uncovered
  surfaces. Keyword scans cannot certify these.
- Replace real-project-shaped operator examples with fictional examples on the
  relevant pilot branches; review their older versions and public PR descriptions
  as well. Do not assume a clean README cleans the repository's history.
- Confirm publication rights and the intended project licence with the owner.
  No MIT/Apache or other licence is selected by this task. Existing notices remain.
- For a runnable article companion, verify a complete synthetic input, documented
  environment, expected outputs, and genuine native Revu create/save/read-back
  evidence. Related source code is not that reproduction package.
- Resolve the experimental branch's acceptance/findings on their own scope; this
  documentation change does not merge draft runtime work or close its gates.

## Interpreting the scanner

`python -m unittest discover -s publication_tests -v`

`python tools/publication_audit.py --repo .`

The script scans raw locally reachable Git objects and rev-list paths. Its stdout
contains only rule counts, object counts, the checked-out commit and limitations;
no matched secrets, personal values or file paths are echoed. Exit 0 means no
pattern matches within the bounded scan, 1 means findings or skipped objects,
and 2 means the scan could not run to completion. It always reports
`ready_for_public_release: false`; a human must review the separate gates.

This review does not authorize force-pushes, ref deletion, visibility changes,
public data uploads, source-rights decisions or removal of legitimate authorship.
