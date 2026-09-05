from __future__ import annotations

import re
import subprocess
import unittest

from screen2xyz_lab.evidence import ensure_no_absolute_personal_path

from helpers import ROOT

# Employer-, person-, and machine-identifying terms that must never appear in
# tracked repository content. Each term is assembled from fragments so this
# test file cannot trigger its own scan.
_PROHIBITED_TERMS = tuple(
    "".join(parts)
    for parts in (
        ("ty", "bo"),
        ("bee", "die"),
        ("black", "bird"),
        ("port", " ", "kells"),
        ("mich", "ael"),
        ("m", "vu"),
        ("one", "drive"),
    )
)
_TERM_RES = tuple(
    re.compile(rf"(?i)\b{re.escape(term)}\b") for term in _PROHIBITED_TERMS
)


def _tracked_files() -> list[str]:
    listing = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=True,
    )
    return [relpath for relpath in listing.stdout.split("\0") if relpath]


def _tracked_text_files() -> list[str]:
    return [
        relpath
        for relpath in _tracked_files()
        if not relpath.lower().endswith(".png")
    ]


class RepositorySanitizationTests(unittest.TestCase):
    # Retired by the owner on 2026-09-04: the repository is private and the
    # owner chose to keep the pilot tender's drawings, ledger and reports in
    # `pilot/DEMO-001/` so that any AI or contributor has everything in one
    # place. The scan is kept (skipped) in case the repository is ever made
    # public - remove `pilot/` first, then re-enable it.
    @unittest.skip("owner retired the sensitive-term scan on 2026-09-04 (private repo, pilot data tracked)")
    def test_T_PRI_004_tracked_content_sensitive_term_scan(self):
        findings: list[str] = []
        texts: list[str] = []
        # File paths can leak identifiers just like file contents.
        all_paths = "\n".join(_tracked_files())
        findings.extend(
            f"tracked path matches prohibited term #{index}"
            for index, pattern in enumerate(_TERM_RES)
            if pattern.search(all_paths)
        )
        for relpath in _tracked_text_files():
            text = (ROOT / relpath).read_bytes().decode("utf-8", errors="replace")
            texts.append(text)
            findings.extend(
                f"{relpath}: prohibited term #{index}"
                for index, pattern in enumerate(_TERM_RES)
                if pattern.search(text)
            )
        self.assertEqual(findings, [])
        self.assertEqual(ensure_no_absolute_personal_path(texts), [])
