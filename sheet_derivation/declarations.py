"""The declarations file (design section 8): the general home for what a
maintainer knows about a workbook that measurement cannot establish. The
tool reads it if present; every artifact marks a field DECLARED rather
than MEASURED wherever it was filled from here instead of from the
capture.

Only the header-row-per-sheet declaration is implemented, because it is
the only one a stage needs today (stage 4). Section 8 also describes
sheet role, outbound boundaries, and external-source states -- none of
those are read or acted on by anything in this repository yet; adding a
key for one of them is a later stage's job, not something to anticipate
here.

Nothing here may name a sheet: this module reads whatever sheet names a
declarations file happens to contain, the same way the loader operates on
whatever `sheets` array a capture happens to contain.
"""

import json
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass(frozen=True)
class Declarations:
    """`header_row_overrides` maps a sheet name to the 1-based row number
    the maintainer declares as that sheet's header row, overriding
    whatever stage 4's own detection would have measured."""

    header_row_overrides: Dict[str, int] = field(default_factory=dict)

    def header_row_override(self, sheet_name: str) -> Optional[int]:
        return self.header_row_overrides.get(sheet_name)


_EMPTY = Declarations(header_row_overrides={})


def load_declarations(path: Optional[str]) -> Declarations:
    """Returns an empty Declarations (no overrides of any kind) if `path`
    is None -- "no declarations file was given" and "a declarations file
    was given but declares nothing for this sheet" are the same case from
    a caller's point of view, and both are legitimate: this build creates
    no declarations content for any real workbook, only the mechanism."""
    if path is None:
        return _EMPTY
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    overrides = raw.get("headerRowOverrides", {})
    return Declarations(header_row_overrides={str(k): int(v) for k, v in overrides.items()})
