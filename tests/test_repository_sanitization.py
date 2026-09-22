from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path
from screen2xyz_lab.evidence import ensure_no_absolute_personal_path
from helpers import ROOT

# Organizational/project identifiers remain forbidden. Public authorship is not
# a secret: do not erase contributor names or licences to pass this check.
_TERMS = tuple("".join(x) for x in (
    ("ty", "bo"), ("bee", "die"), ("black", "bird"), ("port", " kells"),
    ("one", "drive"), ("King", "Road"), ("King ", "Road"),
    ("Lef", "euvre"), ("Hunt", "ingdon"), ("24-", "047"),
))
_PATTERNS = tuple(re.compile(re.escape(x), re.I) for x in _TERMS)

class RepositorySanitizationTests(unittest.TestCase):
    def test_T_PRI_004_tracked_content_sensitive_term_scan(self):
        paths = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
            capture_output=True, check=True, timeout=30).stdout.split(b"\0")
        findings = []
        for raw in paths:
            if not raw:
                continue
            rel = raw.decode("utf-8")
            if Path(rel).parts[0] == "pilot":
                findings.append("private input path")
            data = (ROOT / rel).read_bytes()
            text = data.decode("utf-8", errors="replace") if b"\0" not in data else ""
            if any(p.search(rel) or p.search(text) for p in _PATTERNS):
                findings.append("prohibited identifier in tracked content")
            if text and ensure_no_absolute_personal_path([text]):
                findings.append("personal home path in tracked text")
        self.assertEqual(findings, [])
