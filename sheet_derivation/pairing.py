"""Checks that an app's HTML export and a sheet capture belong together.

Compares the worksheet names the export gives for its Google tables
("Worksheet Name/Qualifier", read by `appside_parse.extract_table_sources`)
with the sheet names the capture records. Reads the export from the input
folder itself, beside the capture's two JSON files, so the check needs no
app-side parse.

Four verdicts:

  - MATCH: every worksheet name is among the capture's sheet names.
  - PARTIAL: some are missing. Reported by name; the run continues.
  - NONE: not one is present. The export and the capture almost certainly
    come from different workbooks, and a mismatched pair still produces
    reports that look valid, so callers STOP unless the user passes an
    explicit override -- the same stance `loader.py` takes when the two
    capture files disagree.
  - UNDECIDABLE: there is nothing to compare (no export in the folder, an
    export naming no Google worksheet, no readable capture file). Reported;
    the run continues.

What this check cannot do: tell sibling versions of one app apart. Two
copies of an app read identically named worksheets, so their captures
pass this check against either export. Matching the Drive folder in each
table's "Source Path" would be needed for that, and is recorded in
STATUS.md as an idea only.

Nothing here names a table, a worksheet or any fact about one app.
"""

import fnmatch
import json
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .appside_parse import extract_table_sources
from .loader import FORMULAS_GLOB_PATTERN, VALUES_GLOB_PATTERN

EXPORT_HTML_NAME = "Application Documentation.html"
OVERRIDE_OPTION = "--allow-mismatch"

VERDICT_MATCH = "match"
VERDICT_PARTIAL = "partial"
VERDICT_NONE = "none"
VERDICT_UNDECIDABLE = "undecidable"


@dataclass(frozen=True)
class PairingResult:
    verdict: str
    export_path: Optional[str]
    capture_path: Optional[str]
    expected_worksheets: Tuple[str, ...]  # the export's Google worksheet names, export order
    present: Tuple[str, ...]
    missing: Tuple[str, ...]
    reason: Optional[str] = None  # set for UNDECIDABLE, and for NONE when the capture lists no sheets

    @property
    def stops(self) -> bool:
        return self.verdict == VERDICT_NONE


def find_export_html(folder: str) -> Optional[str]:
    path = os.path.join(folder, EXPORT_HTML_NAME)
    return path if os.path.isfile(path) else None


def find_capture_file_for_sheet_names(folder: str) -> Optional[str]:
    """The capture file to read sheet names from: the values file if
    exactly one matches (it is the smaller of the two), else the formulas
    file if exactly one matches, else None. The loader separately refuses
    a pair whose two sheet lists differ, so either file is authoritative
    for this purpose."""
    try:
        entries = sorted(os.listdir(folder))
    except OSError:
        return None
    for pattern in (VALUES_GLOB_PATTERN, FORMULAS_GLOB_PATTERN):
        matches = fnmatch.filter(entries, pattern)
        if len(matches) == 1:
            return os.path.join(folder, matches[0])
    return None


def read_capture_sheet_names(capture_path: str) -> Tuple[str, ...]:
    with open(capture_path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    return tuple(s.get("sheetName") for s in doc.get("sheets", []) if s.get("sheetName") is not None)


def compare(
    expected_worksheets: Tuple[str, ...],
    capture_sheet_names: Tuple[str, ...],
    export_path: Optional[str] = None,
    capture_path: Optional[str] = None,
) -> PairingResult:
    if not expected_worksheets:
        return PairingResult(
            verdict=VERDICT_UNDECIDABLE, export_path=export_path, capture_path=capture_path,
            expected_worksheets=(), present=(), missing=(),
            reason="the export names no Google Sheets worksheet for any table",
        )
    sheet_set = set(capture_sheet_names)
    present = tuple(w for w in expected_worksheets if w in sheet_set)
    missing = tuple(w for w in expected_worksheets if w not in sheet_set)
    if not missing:
        verdict = VERDICT_MATCH
    elif present:
        verdict = VERDICT_PARTIAL
    else:
        verdict = VERDICT_NONE
    reason = None
    if verdict == VERDICT_NONE and not capture_sheet_names:
        reason = (
            "the capture file lists no sheets at all in the format sheet_capture.gs writes -- it may "
            "not be a sheet_capture.gs capture"
        )
    return PairingResult(
        verdict=verdict, export_path=export_path, capture_path=capture_path,
        expected_worksheets=expected_worksheets, present=present, missing=missing, reason=reason,
    )


def check_pairing(
    folder: str,
    export_path: Optional[str] = None,
    capture_path: Optional[str] = None,
) -> PairingResult:
    """Runs the check for an input folder. `export_path` and
    `capture_path` default to the export and a capture file found in
    `folder` itself."""
    export_path = export_path or find_export_html(folder)
    if export_path is None:
        return PairingResult(
            verdict=VERDICT_UNDECIDABLE, export_path=None, capture_path=capture_path,
            expected_worksheets=(), present=(), missing=(),
            reason=f"no {EXPORT_HTML_NAME!r} in {folder!r}, so there is no export to compare with",
        )
    capture_path = capture_path or find_capture_file_for_sheet_names(folder)
    if capture_path is None:
        return PairingResult(
            verdict=VERDICT_UNDECIDABLE, export_path=export_path, capture_path=None,
            expected_worksheets=(), present=(), missing=(),
            reason=f"no single capture file in {folder!r} to read sheet names from",
        )
    sources = extract_table_sources(export_path)
    if not sources.qualifier_field_present:
        return PairingResult(
            verdict=VERDICT_UNDECIDABLE, export_path=export_path, capture_path=capture_path,
            expected_worksheets=(), present=(), missing=(),
            reason="the export carries no 'Worksheet Name/Qualifier' row for any table",
        )
    try:
        sheet_names = read_capture_sheet_names(capture_path)
    except (OSError, ValueError) as exc:
        return PairingResult(
            verdict=VERDICT_UNDECIDABLE, export_path=export_path, capture_path=capture_path,
            expected_worksheets=(), present=(), missing=(),
            reason=f"could not read sheet names from {capture_path!r}: {exc}",
        )
    return compare(sources.google_worksheets(), sheet_names, export_path, capture_path)


def format_pairing(result: PairingResult, allow_mismatch: bool = False) -> List[str]:
    """The lines a caller prints. One line on a match; a WARNING naming
    what is missing, or why the check could not decide; a STOP message
    (or, with the override, a WARNING) when nothing matches."""
    n = len(result.expected_worksheets)
    if result.verdict == VERDICT_MATCH:
        return [
            f"Pairing check: all {n} worksheet name(s) the export gives for its Google tables "
            f"appear in the capture."
        ]
    if result.verdict == VERDICT_UNDECIDABLE:
        return [f"WARNING: pairing check could not decide: {result.reason}. Continuing."]
    if result.verdict == VERDICT_PARTIAL:
        return [
            f"WARNING: pairing check: {len(result.missing)} of {n} worksheet name(s) the export "
            f"gives for its Google tables are not in the capture: {list(result.missing)}. "
            f"Tables reading them will have no tab in the join. Continuing."
        ]
    capture = os.path.basename(result.capture_path) if result.capture_path else "the capture"
    head = (
        f"none of the {n} worksheet name(s) the export gives for its Google tables "
        f"({list(result.expected_worksheets)}) appear in {capture}. The export and the capture "
        f"almost certainly come from different workbooks."
    )
    if result.reason:
        head += f" Also: {result.reason}."
    if allow_mismatch:
        return [f"WARNING: pairing check: {head} Continuing because {OVERRIDE_OPTION} was given."]
    return [
        f"STOPPED: pairing check: {head}",
        f"Put the matching export and capture together in one folder. If you are certain they "
        f"belong together, run again with {OVERRIDE_OPTION}.",
    ]
