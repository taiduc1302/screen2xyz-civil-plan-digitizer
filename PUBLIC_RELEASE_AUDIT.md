# Public-source release audit - 2026-09-22

## Scope

The deliverable is an inspectable experimental source snapshot, not production
estimating software or the exact demonstration package from the article.
This file records source cleanup separately from GitHub historical-cache removal.

## Completed preparation

- A full-depth backup included ordinary refs, available PR head refs, discussion
  metadata and release assets. The encrypted archive was downloaded, decrypted,
  restored into a fresh local repository, hash-checked and Git-fsck checked.
- The entire folder of real operator inputs was excluded from ordinary public
  branch/tag histories, including raw PDFs, workbooks, company procedures,
  rendered crops and saved working drawings. It was not relabelled as synthetic.
- A project-specific layer inventory was excluded. Identifying project names,
  tender/drawing identifiers and personal home paths in source comments,
  examples, historical messages and certain capture logs were generalized.
- Original Git author/contributor identities and existing licence notices were
  retained. Rewritten histories have different commit hashes; their previous
  cryptographic signatures cannot validate the rewritten objects.
- The previously retired T-PRI-004 repository check was restored as a real test.
  A fail-closed binary-hash/source policy check and synthetic guard regressions
  were added. Public names are not treated as credentials or erased attribution.
- Non-private PNG fixtures/UI examples were visually inspected. Binary files on
  each branch are hash-allowlisted; new binaries require deliberate review.

## Validation

Current hosted test results are recorded by the publication workflow. Do not
interpret this preparation record, an earlier green build or an absent local
optional dependency as a complete live application test. A later executed-results
section identifies the checked commit and actual suite outcomes.

## Separate historical-hosting limitation

Force-updating ordinary Git branches and tags does not delete GitHub's cached
commit views, server-managed PR refs, historical Actions artifacts or previously
downloaded clones. Those are not certified clean by the source-snapshot check.
An administrator/GitHub Support must complete sensitive-data removal for those
surfaces where applicable. Do not describe this as a completed forensic purge.

## Rights and product claims

Publication retains the existing licence status on each branch. It does not
invent a new licence, grant ownership rights, authorize proprietary-data uploads,
or turn synthetic/unit tests into estimator approval. Live Windows OCR, native
Revu and downstream engineering imports retain their own acceptance gates.
