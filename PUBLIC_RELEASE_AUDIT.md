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

## Executed publication checks

Hosted run: https://github.com/taiduc1302/screen2xyz-civil-plan-digitizer/actions/runs/35752904631

Supplemental optional-geometry/stdio run: https://github.com/taiduc1302/screen2xyz-civil-plan-digitizer/actions/runs/35754740497

Both the main baseline and MCP research snapshots were tested on Windows with Python 3.14.

| Snapshot | Suite | Tests discovered | Skipped | Exit |
|---|---|---:|---:|---:|
| main | `python -m unittest discover -s publication_snapshot_tests -v` | 9 | 0 | 0 |
| main | `python tools/publication_check.py` | - | 0 | 0 |
| main | `python tests/run_all.py` | 42 | 0 | 0 |
| main | `python tests_m1/run_m1_tests.py` | 34 | 0 | 0 |
| main | `python tests_m2/run_m2_tests.py` | 498 | 0 | 0 |
| main | `python tests_civil/run_civil_tests.py` | 113 | 1 | 0 |
| main | `python -m screen2xyz_lab.cli verify-evidence` | - | 0 | 0 |
| research | `python -m unittest discover -s publication_snapshot_tests -v` | 9 | 0 | 0 |
| research | `python tools/publication_check.py` | - | 0 | 0 |
| research | `python tests/run_all.py` | 42 | 0 | 0 |
| research | `python tests_m1/run_m1_tests.py` | 34 | 0 | 0 |
| research | `python tests_m2/run_m2_tests.py` | 501 | 0 | 0 |
| research | `python tests_civil/run_civil_tests.py` | 639 | 57 | 0 |
| research | `python -m screen2xyz_lab.cli verify-evidence` | - | 0 | 0 |
| research with optional geometry and stdio | `python -m unittest discover -s publication_snapshot_tests -v` | 9 | 0 | 0 |
| research with optional geometry and stdio | `python tools/publication_check.py` | - | 0 | 0 |
| research with optional geometry and stdio | `python tests/run_all.py` | 42 | 0 | 0 |
| research with optional geometry and stdio | `python tests_m1/run_m1_tests.py` | 34 | 0 | 0 |
| research with optional geometry and stdio | `python tests_m2/run_m2_tests.py` | 501 | 0 | 0 |
| research with optional geometry and stdio | `python tests_civil/run_civil_tests.py` | 639 | 3 | 0 |
| research with optional geometry and stdio | `python -m screen2xyz_lab.cli verify-evidence` | - | 0 | 0 |

The exact tested SHAs and log hashes are in `publication/validation.json`.
The post-validation commit adds this record only; it does not change runtime code.

**PUBLIC_SOURCE_SNAPSHOT_READY: YES.** This means the reviewed source package, not production use.
**GITHUB_HISTORICAL_CACHE_PURGE: NOT COMPLETED.** The owner must request server-side
cleanup of retained sensitive commit/PR views; this workflow cannot certify their removal.
