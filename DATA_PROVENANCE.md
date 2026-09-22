# Public data provenance

The public source package contains generated OCR fixtures and synthetic tests,
not the real operator drawing set. The input folder containing real drawings,
workbooks, rendered crops and company procedures was removed from ordinary
published branch/tag history, not renamed and relabelled as synthetic.

The retained non-private image fixtures were inventoried and visually reviewed.
`publication/binary_allowlist.json` records hashes for the files on this branch.
Tests generate additional fictional PDFs in temporary directories at run time.
No real drawing is required to run the deterministic tests.

Genericized names in source comments describe anonymized engineering lessons,
not a claim that historical real-machine tests were synthetic or reproducible
from this source package. Existing calibration/colour defaults are examples:
each new drawing needs its own independent calibration and legend review.

Some historical capture logs had machine-path fields redacted for privacy.
Those public copies are not byte-identical to the original private records and
do not replace their hashes as original evidence. Test results reported before
the cleanup are historical; consult current validation results for this release.

Original Git author/contributor identities and licence notices are retained.
This cleanup does not transfer copyright or grant a new licence. Follow the
licence present on the selected branch; the Civil/MCP research branch retains
its existing all-rights-reserved status where no project licence was selected.
